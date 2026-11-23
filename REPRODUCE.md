# Reproduce the one-channel preamp

No proprietary simulator, vendor amplifier checkout, or AI service is required. The reference flow uses the public IIC-OSIC-TOOLS Docker image pinned below (2026.10), Sky130A, Xschem and ngspice. Run from the root of this checkout; make it mountable by Docker. Allow several GB for the PDK/tool image. `build/` is scratch space, not published evidence.

```sh
image=hpretl/iic-osic-tools@sha256:4091b82d77a63e61ff29f4f6de9fd5f00935ae5163c3144d373f6443f7af01c1
docker run -d --rm --name sky130-eeg --shm-size=1g -v "$PWD:/foss/designs" "$image" --wait
eda() { docker exec -w /foss/designs -e PDK=sky130A -e PDKPATH=/foss/pdks/sky130A -e SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice sky130-eeg bash -lc 'exec "$@"' eda "$@"; }
mkdir -p build/core
eda xschem -q -x -n -s --rcfile /foss/designs/xschemrc -o /foss/designs/build/core /foss/designs/afe/xschem/tbci_native_input.sch
cmp build/core/tbci_native_input.spice afe/runs/hiz-size-g/tbci_native_input.spice
```

The frozen netlist includes both physical bias return cells. A simulator user can `.include` it and instantiate `tbci_native_input` directly; see the [ramp/offset bench](afe/benches/native_recovery.spice) for an example with voltages, source resistances, sink polarity and loads. The quoted noise and input impedance are differential and exclude pads. There is no complete layout or extracted netlist yet.

## Stress, mismatch and startup

```sh
eda python3 tools/characterize_hiz.py build/core/tbci_native_input.spice build/stress --stress
eda python3 tools/characterize_hiz.py build/core/tbci_native_input.spice build/mismatch --mismatch
eda ngspice -b afe/benches/native_recovery.spice
```

Use **new** output directory names on a repeat characterization. Compare the resulting `metrics.json` to [stress](afe/runs/hiz-stress-g/metrics.json) and [mismatch](afe/runs/hiz-mismatch-g/metrics.json). These characterize different populations, not combined Monte Carlo yield. The recovery deck loads the frozen netlist, uses real rail ramps, and prints observations at specific times; compare with `offset_step_recovery` in the [replay results](proposal/evidence/replay/metrics.json). Simulator exit code alone does not prove the run reached its final time.

## Evidence and PDF

The [evidence appendix](proposal/evidence.md) gives the dataset, replay command and interpretation. `python3 tools/plot_headroom.py` regenerates the D/E/G comparison figure from the checked-in aggregate results. The historical D and E netlists included alongside G can be passed to the same `--stress` characterization instead of the G netlist.

To rebuild the anonymous PDF on a machine with Pandoc 3+, WeasyPrint and common sans-serif fonts, run `sh tools/build_proposal.sh` from the root. Stop the example container when finished: `docker stop sky130-eeg`.
