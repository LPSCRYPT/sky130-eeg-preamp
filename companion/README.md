# Separate software demonstration: prove a threshold without revealing a score

**Not part of the analog IP or a circuit on the proposed shuttle.** The eventual use case is an assistive interface that releases an approved decision rather than a recording. This runnable Rust example addresses one small part of that problem. It uses generated synthetic samples, not the public PhysioNet EEG replay or the analog outputs.

```sh
cd companion
cargo run --locked --release -p bci-feature-proof -- fixtures/pilot.json
```

The host computes a decoder margin, privately blinds it into a Pedersen commitment, then generates and verifies a Bulletproof that the committed margin falls on the disclosed side of the authorized threshold. The verifier sees the commitment, threshold, direction, public context and proof, not the margin, scores or samples. The CLI also verifies that changing the commitment, threshold or context invalidates the proof. The two-value aggregated proof is 736 binary bytes; its public inputs and transport are additional. The input fixture is deliberately public for reproduction. Fresh OS randomness means proof bytes change between runs.

This is **not a proof of alpha-band power**, that the margin was calculated correctly from a particular EEG window, that a real electrode supplied any sample, or that raw data never left a chip. Those are different claims. A future integrated product would need an authenticated ADC-to-window path, protected computation and memory, enforced output policy and appropriately bound evidence. The host prover is not a constant-time, silicon-qualified secure element. There is deliberately no trusted link from the competition test pads to this program.

Dependencies are pinned in [Cargo.lock](Cargo.lock). The [range-proof API](https://docs.rs/bulletproofs/5.0.0/bulletproofs/struct.RangeProof.html) and [Ristretto implementation](https://docs.rs/curve25519-dalek/4.1.3/) are upstream projects under their own terms. No signing key, setup secret, personal recording or key material is distributed.
