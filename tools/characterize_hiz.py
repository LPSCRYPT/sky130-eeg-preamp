#!/usr/bin/env python3
"""Exercise an Xschem-exported preamp, independently of the frozen input bank."""
import argparse
import hashlib
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess

import numpy as np


def simulate(run, dut, condition):
    corner, temp, vdd, *seeds = condition
    work = run / (f"{corner}_{temp}C_{vdd:.3f}V" + (f"_seed{seeds[0]}" if seeds else ""))
    work.mkdir()
    model = Path(os.environ['PDK_ROOT']) / 'sky130A/libs.tech/ngspice/sky130.lib.spice'
    offsets_dc = ''
    for label, center in (('neg', -.1), ('zero', 0.), ('pos', .1)):
        offsets_dc += (f'dc VDIFF {center-.001:.3f} {center+.001:.3f} 0.001 VCMIN 1.2 2.1 0.45\n'
                       f'wrdata {label}.dat v(cm) v(opout) v(onout) i(vp) i(vn)\n')

    def gains(prefix):
        return '\n'.join(f'ac lin 1 {f} {f}\nlet a = mag(v(opout)-v(onout))\n'
                         f'wrdata {prefix}_{f}.dat a' for f in (50, 60))

    deck = f'''Physical differential input preamp: ideal bench supplies, synthetic input, no pad or ADC
.lib "{model}" {corner}
.include "{dut}"
.temp {temp}
.options reltol=1e-5 abstol=1e-15 vntol=1e-9
VDD avdd 0 {vdd}
IREF ref 0 8u
VRETURN vref 0 1.65
VCMIN cm 0 DC 1.65 AC 0
VDIFF diff 0 DC 0 AC 1
EP psrc cm diff 0 0.5
EN nsrc cm diff 0 -0.5
RP psrc ptest 0.001
RN nsrc ntest 0.001
VP ptest inp 0
VN ntest inn 0
XDUT avdd 0 vref ref inp inn opout onout {dut.stem}
* Nominal receiver surrogate on each drain, NOT a connected PGA/ADC.
RLP opout vref 4.915meg
RLN onout vref 4.915meg
CLP opout vref 100f
CLN onout vref 100f
.control
set wr_singlescale
set wr_vecnames
save all onoise_spectrum inoise_spectrum onoise_total inoise_total
op
wrdata op.dat v(opout) v(onout) i(vdd) i(vp) i(vn)
ac lin 1 10 10
let ad = real((v(opout)-v(onout))/(v(inp)-v(inn)))
let zin = mag((v(inp)-v(inn))/((i(vp)-i(vn))/2))
wrdata input.dat ad zin
noise v(opout,onout) VDIFF lin 891 0.5 45
wrdata noise.dat inoise_total
* Bias return fixed at 1.65 V; positive and negative electrodes moved together.
{offsets_dc}
alter RP = 10000.001
{gains('diff')}
alter @VDIFF[acmag] = 0
alter @VCMIN[acmag] = 1
{gains('cm')}
alter RP = 0.001
alter RN = 10000.001
{gains('cm_n')}
alter @VDIFF[acmag] = 1
alter @VCMIN[acmag] = 0
{gains('diff_n')}
quit
.endc
.end
'''
    if seeds:
        # Random model parameters are evaluated when the circuit is loaded.
        # Set the seed BEFORE sourcing that circuit, not between its analyses.
        circuit, analysis = deck.split('.control\n', 1)
        (work / 'sample.spice').write_text(circuit + '.end\n')
        deck = f"Mismatch driver\n.control\nsetseed {seeds[0]}\nsource sample.spice\n" + analysis
    (work / 'testbench.spice').write_text(deck)
    with (work / 'ngspice.log').open('w') as log:
        subprocess.run(['ngspice', '-b', 'testbench.spice'], cwd=work, stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=180)
    text = (work / 'ngspice.log').read_text().lower()
    if any(s in text for s in ('error:', 'aborted', 'fatal', 'timestep too small', 'no data saved')):
        raise RuntimeError(f'Non-clean simulator result: {work}/ngspice.log')

    def data(name, rows, columns):
        a = np.loadtxt(work / (name + '.dat'), skiprows=1, ndmin=2)
        if a.shape != (rows, columns) or not np.isfinite(a).all():
            raise ValueError(f'{name} invalid in {work}: {a.shape}')
        return a

    _, outp, outn, supply, ip, inn = data('op', 1, 6)[0]
    _, gain, zin = data('input', 1, 3)[0]
    noise = data('noise', 1, 2)[0, 1]
    offsets = []
    for label, center in (('neg', -.1), ('zero', 0.), ('pos', .1)):
        sweep = data(label, 9, 6)
        for cm in (1.2, 1.65, 2.1):
            a = sweep[np.isclose(sweep[:, 1], cm)]
            np.testing.assert_allclose(a[:, 0], [center-.001, center, center+.001], atol=1e-9)
            d = a[:, 2] - a[:, 3]
            k = 1
            offsets.append({'input_cm_V': cm, 'differential_offset_V': round(float(a[k, 0]), 3),
                            'outp_V': a[k, 2], 'outn_V': a[k, 3],
                            'incremental_gain_V_per_V': (d[k+1] - d[k-1]) / .002,
                            'max_abs_input_current_A': float(np.max(np.abs(a[k, 4:6])))})
    def rejection(suffix):
        cmrr = {}
        for f in (50, 60):
            fd, adm = data(f'diff{suffix}_{f}', 1, 2)[0]
            fc, acm = data(f'cm{suffix}_{f}', 1, 2)[0]
            assert fd == fc == f
            cmrr[str(f)] = 20 * math.log10(adm/acm)
        return cmrr
    return {'corner': corner, 'temperature_C': temp, 'supply_V': vdd,
            'mismatch_seed': seeds[0] if seeds else None, 'output_differential_offset_V': outp-outn,
            'supply_current_A_including_reference_leg': -supply,
            'output_common_mode_V': (outp + outn)/2, 'max_nominal_input_current_A': max(abs(ip), abs(inn)),
            'gain_10Hz_V_per_V': gain, 'differential_Zin_10Hz_ohm': zin,
            'input_noise_0p5_to_45Hz_Vrms': noise, 'source_imbalance_10k_CMRR_dB': rejection(''),
            'negative_leg_imbalance_10k_CMRR_dB': rejection('_n'),
            'dc_offset_cases': offsets}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('netlist', type=Path); p.add_argument('output', type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--stress', action='store_true', help='also run six selected stress combinations (not a full PVT grid)')
    mode.add_argument('--mismatch', action='store_true', help='eight seeded TT local-mismatch samples (not a yield estimate)')
    args = p.parse_args()
    if os.environ.get('PDK') != 'sky130A':
        p.error('Use tools/eda.py to select Sky130A')
    dut = args.netlist.resolve(strict=True); run = args.output.resolve(); run.mkdir(parents=True, exist_ok=False)
    conditions = [('tt', 27, 3.3)]
    if args.stress:
        conditions += [('ss', -40, 3.135), ('ss', 110, 3.135), ('ff', -40, 3.465),
                       ('ff', 110, 3.465), ('sf', 110, 3.135), ('fs', -40, 3.135)]
    if args.mismatch:
        conditions = [('tt_mm', 27, 3.3, seed) for seed in range(301, 309)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda c: simulate(run, dut, c), conditions))
    summary = {'dut_sha256': hashlib.sha256(dut.read_bytes()).hexdigest(), 'conditions':len(results),
               'scope':'Isolated pre-layout channel; ideal supplies/reference, modeled bench resistors. No pads, driver, extracted parasitics or startup qualification.',
               'results': results}
    (run/'metrics.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
    for r in results:
        print(r['corner'],r['temperature_C'],r['supply_V'],'Z(Mohm)',round(r['differential_Zin_10Hz_ohm']/1e6,2),
              'noise(uVrms)',round(r['input_noise_0p5_to_45Hz_Vrms']*1e6,3),'gain',round(r['gain_10Hz_V_per_V'],3),
              'CMRR(dB)',round(min(r['source_imbalance_10k_CMRR_dB'].values()),2),
              'min offset gain',round(min(x['incremental_gain_V_per_V'] for x in r['dc_offset_cases']),3))


if __name__ == '__main__':
    main()
