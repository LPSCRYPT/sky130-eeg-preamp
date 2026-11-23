//! Hidden-margin threshold evidence. Native acquisition and DSP remain trusted.

use bci_signal_core::{decode, model_digest, validate_fixture, Fixture};
use bulletproofs::{BulletproofGens, PedersenGens, RangeProof};
use curve25519_dalek::{ristretto::CompressedRistretto, scalar::Scalar};
use merlin::Transcript;
use rand_core::{CryptoRng, RngCore};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use zeroize::{Zeroize, Zeroizing};

pub const MAX_MARGIN: u64 = 1 << 34;
const RANGE_BITS: usize = 64;
const RANGE_COUNT: usize = 2;
// 32 bytes per point/scalar: 9 fixed elements and 2*log2(64*2) IPP elements.
const PROOF_BYTES: usize = (9 + 2 * 7) * 32;

/// Public fixture identity, obtained independently by the verifier's policy layer.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PublicContext {
    pub context_digest: [u8; 32],
    pub channels: u32,
    pub samples_per_channel: u32,
    pub sample_rate_hz: u32,
    pub margin_threshold: u64,
    pub model_digest: [u8; 32],
}

impl PublicContext {
    pub fn from_fixture(fixture: &Fixture) -> Result<Self, String> {
        validate_fixture(fixture).map_err(|_| "fixture validation failed".to_owned())?;
        let context = Self {
            context_digest: fixture.context_digest,
            channels: fixture.config.channels as u32,
            samples_per_channel: fixture.config.samples_per_channel as u32,
            sample_rate_hz: fixture.config.sample_rate_hz,
            margin_threshold: fixture.config.margin_threshold,
            model_digest: model_digest(fixture),
        };
        context.validate()?;
        Ok(context)
    }

    fn validate(&self) -> Result<(), String> {
        if !(1..=8).contains(&self.channels)
            || !matches!(self.samples_per_channel, 250 | 500)
            || self.sample_rate_hz != 250
            || !(1..=MAX_MARGIN).contains(&self.margin_threshold)
        {
            return Err("unsupported public configuration".to_owned());
        }
        Ok(())
    }

    /// Canonical digest of all public fixture fields, not of private samples.
    /// Authentication and expansion of context_digest remain the caller's duty.
    pub fn binding_digest(&self) -> [u8; 32] {
        let mut hash = Sha256::new();
        hash.update(b"bci-feature-context-v1\0");
        hash.update(self.context_digest);
        hash.update(self.channels.to_le_bytes());
        hash.update(self.samples_per_channel.to_le_bytes());
        hash.update(self.sample_rate_hz.to_le_bytes());
        hash.update(self.margin_threshold.to_le_bytes());
        hash.update(self.model_digest);
        hash.finalize().into()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ThresholdClaim {
    AtOrAbove,
    Below,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FeatureStatement {
    pub context: PublicContext,
    pub claim: ThresholdClaim,
    pub commitment: [u8; 32],
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FeatureEvidence {
    pub statement: FeatureStatement,
    pub proof: Vec<u8>,
}

/// Reusable, public generators. No trusted setup and no retained private witness.
pub struct FeatureProver {
    bp: BulletproofGens,
    pc: PedersenGens,
}

impl Default for FeatureProver {
    fn default() -> Self {
        Self::new()
    }
}

impl FeatureProver {
    pub fn new() -> Self {
        Self {
            bp: BulletproofGens::new(RANGE_BITS, RANGE_COUNT),
            pc: PedersenGens::default(),
        }
    }

    /// Computes the shared native decoder and proves the actual threshold branch.
    /// The caller must supply fresh production-quality entropy in production.
    /// This does not prove the native decoder or authorize a command.
    pub fn prove<R: RngCore + CryptoRng>(
        &self,
        fixture: &Fixture,
        rng: &mut R,
    ) -> Result<FeatureEvidence, String> {
        let context = PublicContext::from_fixture(fixture)?;
        let mut decision = decode(fixture).map_err(|_| "native decoder failed".to_owned())?;
        let result = self.prove_margin(context, decision.margin, rng);
        decision.margin.zeroize();
        decision.scores.zeroize();
        decision.winner.zeroize();
        decision.command.zeroize();
        decision.clipped.zeroize();
        result
    }

    fn prove_margin<R: RngCore + CryptoRng>(
        &self,
        context: PublicContext,
        margin: u64,
        rng: &mut R,
    ) -> Result<FeatureEvidence, String> {
        context.validate()?;
        if margin > MAX_MARGIN {
            return Err("margin exceeds decoder bound".to_owned());
        }
        let threshold = context.margin_threshold;
        let claim = if margin >= threshold {
            ThresholdClaim::AtOrAbove
        } else {
            ThresholdClaim::Below
        };
        let values = Zeroizing::new(match claim {
            ThresholdClaim::AtOrAbove => [margin - threshold, MAX_MARGIN - margin],
            ThresholdClaim::Below => [margin, threshold - 1 - margin],
        });
        let blinding = Zeroizing::new(Scalar::random(rng));
        let blindings = Zeroizing::new([*blinding, -*blinding]);
        let statement = FeatureStatement {
            context,
            claim,
            commitment: self
                .pc
                .commit(Scalar::from(margin), *blinding)
                .compress()
                .to_bytes(),
        };
        let mut transcript = transcript(&statement);
        let (proof, commitments) = RangeProof::prove_multiple_with_rng(
            &self.bp,
            &self.pc,
            &mut transcript,
            &values[..],
            &blindings[..],
            RANGE_BITS,
            rng,
        )
        .map_err(|_| "range proof construction failed".to_owned())?;
        // Reject any implementation drift between prover arithmetic and verifier relation.
        if commitments.as_slice() != self.range_commitments(&statement)?.as_slice() {
            return Err("range commitment relation mismatch".to_owned());
        }
        Ok(FeatureEvidence {
            statement,
            proof: proof.to_bytes(),
        })
    }

    /// Verify a public statement and borrowed proof against independently approved
    /// context. Wire consumers must derive the statement from authenticated fields.
    pub fn verify<R: RngCore + CryptoRng>(
        &self,
        statement: &FeatureStatement,
        proof_bytes: &[u8],
        expected_context: &PublicContext,
        rng: &mut R,
    ) -> Result<(), String> {
        expected_context.validate()?;
        if &statement.context != expected_context {
            return Err("public context does not match approved policy".to_owned());
        }
        if proof_bytes.len() != PROOF_BYTES {
            return Err("unexpected proof length".to_owned());
        }
        let commitments = self.range_commitments(statement)?;
        let proof = RangeProof::from_bytes(proof_bytes)
            .map_err(|_| "invalid range proof encoding".to_owned())?;
        proof
            .verify_multiple_with_rng(
                &self.bp,
                &self.pc,
                &mut transcript(statement),
                &commitments,
                RANGE_BITS,
                rng,
            )
            .map_err(|_| "range proof verification failed".to_owned())
    }

    fn range_commitments(
        &self,
        statement: &FeatureStatement,
    ) -> Result<[CompressedRistretto; 2], String> {
        statement.context.validate()?;
        let commitment = CompressedRistretto(statement.commitment)
            .decompress()
            .ok_or_else(|| "invalid margin commitment encoding".to_owned())?;
        let threshold = statement.context.margin_threshold;
        Ok(match statement.claim {
            ThresholdClaim::AtOrAbove => [
                (commitment - Scalar::from(threshold) * self.pc.B).compress(),
                (Scalar::from(MAX_MARGIN) * self.pc.B - commitment).compress(),
            ],
            ThresholdClaim::Below => [
                commitment.compress(),
                (Scalar::from(threshold - 1) * self.pc.B - commitment).compress(),
            ],
        })
    }
}

fn transcript(statement: &FeatureStatement) -> Transcript {
    let mut transcript = Transcript::new(b"bci-hidden-margin-bulletproof-v1");
    transcript.append_message(b"public-context", &statement.context.binding_digest());
    transcript.append_message(
        b"claim",
        &[match statement.claim {
            ThresholdClaim::AtOrAbove => 1,
            ThresholdClaim::Below => 0,
        }],
    );
    transcript.append_u64(b"maximum-margin", MAX_MARGIN);
    transcript.append_u64(b"range-bits", RANGE_BITS as u64);
    transcript.append_u64(b"range-count", RANGE_COUNT as u64);
    transcript.append_message(b"margin-commitment", &statement.commitment);
    transcript
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand_core::OsRng;

    fn context(threshold: u64) -> PublicContext {
        PublicContext {
            context_digest: [42; 32],
            channels: 8,
            samples_per_channel: 500,
            sample_rate_hz: 250,
            margin_threshold: threshold,
            model_digest: [7; 32],
        }
    }

    #[test]
    fn inclusive_upper_and_strict_lower_threshold_boundaries() {
        let prover = FeatureProver::new();
        let mut rng = OsRng;
        for (margin, threshold, claim) in [
            (0, 1, ThresholdClaim::Below),
            (MAX_MARGIN - 1, MAX_MARGIN, ThresholdClaim::Below),
            (MAX_MARGIN, MAX_MARGIN, ThresholdClaim::AtOrAbove),
            (1, 1, ThresholdClaim::AtOrAbove),
        ] {
            let context = context(threshold);
            let evidence = prover
                .prove_margin(context.clone(), margin, &mut rng)
                .unwrap();
            assert_eq!(evidence.statement.claim, claim);
            assert!(prover
                .verify(&evidence.statement, &evidence.proof, &context, &mut rng)
                .is_ok());
        }
        assert!(prover
            .prove_margin(context(1), MAX_MARGIN + 1, &mut rng)
            .is_err());
        assert!(prover.prove_margin(context(0), 0, &mut rng).is_err());
        assert!(prover
            .prove_margin(context(MAX_MARGIN + 1), 0, &mut rng)
            .is_err());
    }

    #[test]
    fn proof_rejects_rebinding_even_with_matching_expected_context() {
        let prover = FeatureProver::new();
        let mut rng = OsRng;
        let evidence = prover.prove_margin(context(10), 100, &mut rng).unwrap();
        for mutation in 0..5 {
            let mut changed = evidence.clone();
            match mutation {
                0 => changed.statement.context.context_digest[0] ^= 1,
                1 => changed.statement.context.model_digest[0] ^= 1,
                2 => changed.statement.context.margin_threshold += 1,
                3 => changed.statement.claim = ThresholdClaim::Below,
                _ => {
                    let point = CompressedRistretto(changed.statement.commitment)
                        .decompress()
                        .unwrap();
                    changed.statement.commitment = (point + prover.pc.B).compress().to_bytes();
                }
            }
            assert!(prover
                .verify(
                    &changed.statement,
                    &changed.proof,
                    &changed.statement.context,
                    &mut rng
                )
                .is_err());
        }
    }
}
