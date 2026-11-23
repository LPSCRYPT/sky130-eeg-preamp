//! Bit-exact engineering decoder shared by all three reference modes.
//! This is not a clinically validated EEG classifier.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub const RAW_MIN: i32 = -8_388_608;
pub const RAW_MAX: i32 = 8_388_607;
pub const MAX_SCORE: u64 = 1_u64 << 34;
pub const ABSTAIN: u8 = 255;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Config {
    pub channels: usize,
    pub samples_per_channel: usize,
    pub sample_rate_hz: u32,
    pub margin_threshold: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Fixture {
    pub config: Config,
    pub context_digest: [u8; 32],
    pub samples: Vec<Vec<i32>>,
    pub coefficients: Vec<Vec<[i16; 2]>>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Decision {
    pub command: u8,
    pub winner: u8,
    pub scores: [u64; 4],
    pub margin: u64,
    pub clipped: bool,
}

pub fn validate_fixture(f: &Fixture) -> Result<(), String> {
    if !(1..=8).contains(&f.config.channels) {
        return Err("channel count must be 1..=8".into());
    }
    if !matches!(f.config.samples_per_channel, 250 | 500) {
        return Err("window must contain 250 or 500 samples per channel".into());
    }
    if f.config.sample_rate_hz != 250 {
        return Err("sample rate must be 250 Hz".into());
    }
    if !(1..=MAX_SCORE).contains(&f.config.margin_threshold) {
        return Err("margin threshold must be in 1..=2^34".into());
    }
    if f.samples.len() != f.config.channels {
        return Err("sample channel count does not match configuration".into());
    }
    for channel in &f.samples {
        if channel.len() != f.config.samples_per_channel {
            return Err("sample window length does not match configuration".into());
        }
        if channel.iter().any(|x| !(RAW_MIN..=RAW_MAX).contains(x)) {
            return Err("sample is outside signed 24-bit range".into());
        }
    }
    if f.coefficients.len() != 4 {
        return Err("model must contain four targets".into());
    }
    for target in &f.coefficients {
        if target.len() != 250 {
            return Err("each target must contain 250 coefficient phases".into());
        }
        if target.iter().flatten().any(|&v| v == i16::MIN) {
            return Err("coefficient must be in -32767..=32767".into());
        }
    }
    Ok(())
}

/// Arithmetic right shift implements floor(x / 256).
/// Precondition: x is a valid signed 24-bit ADC code.
#[inline]
pub fn quantize(x: i32) -> i16 {
    (x >> 8) as i16
}

pub fn decode(f: &Fixture) -> Result<Decision, String> {
    validate_fixture(f)?;
    let denominator = 32_768_i64 * f.config.samples_per_channel as i64;
    let mut scores = [0_u64; 4];
    let mut clipped = false;

    for channel in &f.samples {
        let mut sums = [[0_i64; 2]; 4];
        let mut phase = 0;
        for &raw in channel {
            clipped |= raw == RAW_MIN || raw == RAW_MAX;
            let sample = i64::from(quantize(raw));
            for (target, sum) in sums.iter_mut().enumerate() {
                let coefficient = f.coefficients[target][phase];
                sum[0] += sample * i64::from(coefficient[0]);
                sum[1] += sample * i64::from(coefficient[1]);
            }
            phase += 1;
            if phase == 250 {
                phase = 0;
            }
        }
        // Validated bounds give |sum| < 2^39. Euclidean division, unlike
        // truncation toward zero, preserves the specified negative rounding.
        for (score, sum) in scores.iter_mut().zip(sums) {
            let re = sum[0].div_euclid(denominator);
            let im = sum[1].div_euclid(denominator);
            *score += (re * re + im * im) as u64;
        }
    }

    let mut winner = 0_usize;
    for target in 1..4 {
        if scores[target] > scores[winner] {
            winner = target;
        }
    }
    let runner_up = scores
        .iter()
        .enumerate()
        .filter(|(target, _)| *target != winner)
        .map(|(_, &score)| score)
        .max()
        .expect("there are four targets");
    let margin = scores[winner] - runner_up;
    let command = if clipped || margin < f.config.margin_threshold {
        ABSTAIN
    } else {
        winner as u8
    };
    Ok(Decision {
        command,
        winner: winner as u8,
        scores,
        margin,
        clipped,
    })
}

/// Versioned model identity; dimensions are encoded to avoid concatenation
/// ambiguity even if a caller hashes an invalid model before validation.
pub fn model_digest(f: &Fixture) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"TBCI-MODEL-v1\0");
    hash.update((f.coefficients.len() as u64).to_le_bytes());
    for target in &f.coefficients {
        hash.update((target.len() as u64).to_le_bytes());
        for pair in target {
            hash.update(pair[0].to_le_bytes());
            hash.update(pair[1].to_le_bytes());
        }
    }
    hash.finalize().into()
}

/// Public statement identity. The caller must separately authenticate the
/// acquisition/session represented by context_digest; hashing is not attestation.
pub fn statement_context(f: &Fixture) -> [u8; 32] {
    let mut hash = Sha256::new();
    hash.update(b"TBCI-CONTEXT-v1\0");
    hash.update(f.context_digest);
    hash.update((f.config.channels as u64).to_le_bytes());
    hash.update((f.config.samples_per_channel as u64).to_le_bytes());
    hash.update(f.config.sample_rate_hz.to_le_bytes());
    hash.update(f.config.margin_threshold.to_le_bytes());
    hash.update(model_digest(f));
    hash.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn constant_fixture(raw: i32) -> Fixture {
        let mut coefficients = vec![vec![[0_i16; 2]; 250]; 4];
        coefficients[0].fill([32767, 0]);
        Fixture {
            config: Config {
                channels: 1,
                samples_per_channel: 250,
                sample_rate_hz: 250,
                margin_threshold: 1,
            },
            context_digest: [7; 32],
            samples: vec![vec![raw; 250]],
            coefficients,
        }
    }

    #[test]
    fn negative_quantization_and_projection_use_floor() {
        assert_eq!(quantize(-1), -1);
        assert_eq!(quantize(-256), -1);
        assert_eq!(quantize(-257), -2);
        assert_eq!(quantize(RAW_MIN), i16::MIN);
        assert_eq!(quantize(RAW_MAX), i16::MAX);
        let decision = decode(&constant_fixture(-1)).unwrap();
        assert_eq!(decision.scores, [1, 0, 0, 0]);
        assert_eq!(decision.command, 0);
    }

    #[test]
    fn tie_breaking_is_stable_but_positive_threshold_abstains() {
        let mut fixture = constant_fixture(-256);
        fixture.coefficients[1].fill([32767, 0]);
        let decision = decode(&fixture).unwrap();
        assert_eq!(decision.winner, 0);
        assert_eq!(decision.margin, 0);
        assert_eq!(decision.command, ABSTAIN);
    }

    #[test]
    fn clipped_input_forces_abstention_despite_large_margin() {
        let decision = decode(&constant_fixture(RAW_MIN)).unwrap();
        assert!(decision.margin >= 1);
        assert!(decision.clipped);
        assert_eq!(decision.command, ABSTAIN);
    }

    #[test]
    fn malformed_windows_and_out_of_range_codes_are_rejected() {
        let mut fixture = constant_fixture(RAW_MIN - 1);
        assert!(decode(&fixture).is_err());
        fixture.samples[0].fill(RAW_MAX + 1);
        assert!(decode(&fixture).is_err());
        fixture.samples[0].fill(0);
        fixture.samples[0].pop();
        assert!(decode(&fixture).is_err());
    }

    #[test]
    fn threshold_cannot_bypass_abstention_or_integer_bounds() {
        let mut fixture = constant_fixture(-256);
        fixture.config.margin_threshold = 0;
        assert!(decode(&fixture).is_err());
        fixture.config.margin_threshold = MAX_SCORE + 1;
        assert!(decode(&fixture).is_err());
    }
}
