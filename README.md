# Sky130 EEG preamplifier with electrode-offset headroom

**[Read the anonymous Chipalooza #4 proposal (PDF)](proposal/chipalooza-4-eeg-preamp.pdf)** · [Design and target specifications](proposal/proposal.md) · [Measurement plan](proposal/measurement.md) · [Simulation evidence](proposal/evidence.md)

One reusable, DC-coupled differential preamplifier for weak biopotentials on a 3.3 V Sky130A analog supply. The design question: can a small EEG variation be amplified in the presence of a much larger differential electrode offset, without first nulling that offset? A native NMOS input pair with resistive source degeneration trades voltage gain for headroom. The block amplifies the offset too; it does **not** cancel DC.

| Read or reuse | Artifact |
|---|---|
| Editable one-channel circuit and symbol | [Xschem schematic](afe/xschem/tbci_native_input.sch), [symbol](afe/xschem/tbci_native_input.sym), [drawing](afe/runs/hiz-size-g/tbci_native_input.svg) |
| SPICE integration | [Hierarchical subcircuit](afe/runs/hiz-size-g/tbci_native_input.spice) · pin order: `AVDD AVSS VCM IREF_SINK VINP VINN OUTP OUTN` |
| Core operating-point, noise, rejection and offset sweeps | [Seven selected process/temperature/supply conditions](afe/runs/hiz-stress-g/metrics.json) · [eight separate typical-corner mismatch seeds](afe/runs/hiz-mismatch-g/metrics.json) |
| Independent review | [Reproduce with open tools](REPRODUCE.md) · [measurement schematic](proposal/bench.svg) · [competition requirements](https://opencircuitdesign.com/chipalooza/rules-4.html) |
| Optional trusted-BCI software demonstrator | [Prove a private decoder margin is above or below a threshold](companion/README.md); runs on a host with synthetic data, not on the analog chip. |

**What exists:** transistor-level core, editable sources, open testbenches and pre-layout results. Nominal gain is 4.16 V/V, not programmable. Across 63 offset/common-mode operating points in seven selected conditions, incremental gain stayed at or above 95.1% of each condition’s nominal 10 Hz gain. Coverage is not a yield estimate. Output common mode is about 2.70 V at nominal supply; outputs are not 1.8 V ADC pins.

**EEG replay:** all seven recorded-waveform simulations completed. With ±100 mV electrode offset and a 10 kΩ imbalance on either input, the worst error was **3.38% RMS with fixed gain calibration**, relative to the recorded signal RMS. No output entered the defined rail guard at any sample instant. [Waveform overlay](proposal/evidence/replay/waveform.svg) · [conditions and complete results](proposal/evidence/replay/metrics.json). This measures noiseless schematic fidelity, not live EEG, pad noise or silicon performance.

**What is proposed:** low-leakage pad selection, current-reference adapter, output measurement buffers, layout, extracted verification and packaged-silicon characterization. These are not completed sign-offs. For benchtop signal replay only; no connection to people. This is the analog input stage of a possible future trusted BCI, **not** an ADC, eight-channel acquisition system, secure element or ZK circuit. Raw analog outputs are intentionally observable on this test chip.

## License and data

Original circuit sources, tools and documentation: [Apache License 2.0](LICENSE). PhysioNet data are separately licensed; attribution, preprocessing and source are in the [evidence notes](proposal/evidence.md). Sky130 device libraries come from the pinned EDA environment, under their own licenses. The single-channel core does not depend on a vendor instrumentation-amplifier checkout.
