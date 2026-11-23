use bci_feature_proof::{FeatureProver, PublicContext, MAX_MARGIN};
use bci_signal_core::Fixture;
use curve25519_dalek::{constants::RISTRETTO_BASEPOINT_POINT, ristretto::CompressedRistretto};
use rand_core::OsRng;
use serde_json::json;
use std::{env, fs, process::ExitCode, time::Instant};
use zeroize::{Zeroize, Zeroizing};

struct PrivateFixture(Fixture);

impl Drop for PrivateFixture {
    fn drop(&mut self) {
        self.0.samples.zeroize();
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    let path = args
        .next()
        .ok_or_else(|| "usage: bci-feature-proof FIXTURE.json".to_owned())?;
    if args.next().is_some() {
        return Err("usage: bci-feature-proof FIXTURE.json".to_owned());
    }
    let input = Zeroizing::new(fs::read(path).map_err(|_| "cannot read fixture".to_owned())?);
    let fixture = PrivateFixture(
        serde_json::from_slice::<Fixture>(&input).map_err(|_| "invalid fixture JSON".to_owned())?,
    );
    drop(input);
    let context = PublicContext::from_fixture(&fixture.0)?;
    let start = Instant::now();
    let prover = FeatureProver::new();
    let generator_ms = start.elapsed().as_secs_f64() * 1000.0;
    let mut rng = OsRng;
    let start = Instant::now();
    let evidence = prover.prove(&fixture.0, &mut rng)?;
    let prove_including_native_decode_ms = start.elapsed().as_secs_f64() * 1000.0;
    drop(fixture);
    let start = Instant::now();
    prover.verify(&evidence.statement, &evidence.proof, &context, &mut rng)?;
    let verify_ms = start.elapsed().as_secs_f64() * 1000.0;

    // Use valid curve points, not merely a malformed encoding test.
    let mut substituted = evidence.clone();
    let point = CompressedRistretto(substituted.statement.commitment)
        .decompress()
        .ok_or_else(|| "prover returned invalid commitment".to_owned())?;
    substituted.statement.commitment = (point + RISTRETTO_BASEPOINT_POINT).compress().to_bytes();
    let start = Instant::now();
    let substituted_commitment_rejected = prover
        .verify(
            &substituted.statement,
            &substituted.proof,
            &context,
            &mut rng,
        )
        .is_err();
    let substituted_commitment_verify_ms = start.elapsed().as_secs_f64() * 1000.0;

    let mut changed_threshold = evidence.clone();
    changed_threshold.statement.context.margin_threshold = if context.margin_threshold == MAX_MARGIN
    {
        MAX_MARGIN - 1
    } else {
        context.margin_threshold + 1
    };
    let start = Instant::now();
    // Match the altered expected policy so rejection exercises cryptography,
    // rather than only the expected-context equality guard.
    let changed_policy_threshold_rejected = prover
        .verify(
            &changed_threshold.statement,
            &changed_threshold.proof,
            &changed_threshold.statement.context,
            &mut rng,
        )
        .is_err();
    let changed_policy_threshold_verify_ms = start.elapsed().as_secs_f64() * 1000.0;

    let mut changed_session = evidence.clone();
    changed_session.statement.context.context_digest[0] ^= 1;
    let start = Instant::now();
    let changed_session_context_rejected = prover
        .verify(
            &changed_session.statement,
            &changed_session.proof,
            &changed_session.statement.context,
            &mut rng,
        )
        .is_err();
    let changed_session_context_verify_ms = start.elapsed().as_secs_f64() * 1000.0;

    if !(substituted_commitment_rejected
        && changed_policy_threshold_rejected
        && changed_session_context_rejected)
    {
        return Err("a negative verification unexpectedly succeeded".to_owned());
    }
    let proof_bytes = evidence.proof.len();
    let report = json!({
        "mode": "trusted_native_dsp_hidden_margin",
        "proof_system": "bulletproofs-5.0.0/ristretto255",
        "randomness": "development_host_os_rng_not_qualified_silicon_entropy",
        "range_bits": 64,
        "range_count": 2,
        "maximum_margin": MAX_MARGIN,
        "proof_bytes": proof_bytes,
        "margin_commitment_bytes": 32,
        "evidence": evidence,
        "verification": {
            "valid": true,
            "substituted_commitment_rejected": substituted_commitment_rejected,
            "changed_policy_threshold_rejected": changed_policy_threshold_rejected,
            "changed_session_context_rejected": changed_session_context_rejected
        },
        "timings_ms": {
            "public_generator_construction": generator_ms,
            "prove_including_native_decode_and_context_hash": prove_including_native_decode_ms,
            "verify": verify_ms,
            "substituted_commitment_verify": substituted_commitment_verify_ms,
            "changed_policy_threshold_verify": changed_policy_threshold_verify_ms,
            "changed_session_context_verify": changed_session_context_verify_ms
        }
    });
    println!(
        "{}",
        serde_json::to_string(&report).map_err(|_| "report serialization failed".to_owned())?
    );
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("bci-feature-proof: {message}");
            ExitCode::FAILURE
        }
    }
}
