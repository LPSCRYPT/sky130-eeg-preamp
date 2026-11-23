#!/usr/bin/env python3
"""Replay the attributed 160 Hz EEG on the Rev G Sky130A schematic (no Python dependencies).
From hardware/: python3 tools/eda.py python3 tools/replay_eeg.py --out proposal/evidence/replay
For a native installation, run this script directly with --pdk /path/to/sky130A.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from bisect import bisect_left
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import fmean
from string import Template

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'afe/replay'
DUT = ROOT / 'afe/runs/hiz-size-g/tbci_native_input.spice'
RECOVERY = ROOT / 'afe/benches/native_recovery.spice'
RATE = 160
START = 3 / RATE  # two periods at zero EEG, then one to ramp to the first recorded value
END = START + 4
RAIL_GUARD = 0.050
# A physical series resistance on each source, not a change in the on-chip bias resistors.
CASES = [('balanced', 0, 10000, 10000)] + [
    (leg, mv, rp, rn) for mv in (-100, 0, 100)
    for leg, rp, rn in [('P_high', 20000, 10000), ('N_high', 10000, 20000)]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(work, deck, env):
    (work / 'bench.spice').write_text(deck)
    run = subprocess.run(['ngspice', '-b', 'bench.spice'], cwd=work, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if run.returncode or re.search(r'simulation\(s\) aborted|timestep too small|fatal error', run.stdout, re.I):
        raise RuntimeError(f'ngspice failed in {work.name}:\n{run.stdout[-3000:]}')
    return run.stdout


def interpolate(times, rows, t):
    i = bisect_left(times, t)
    if i < len(times) and abs(times[i] - t) < 1e-12:
        return rows[i][1:]
    if not 0 < i < len(times):
        raise ValueError(f'missing transient data at {t} s')
    a, b = rows[i-1], rows[i]
    k = (t - a[0]) / (b[0] - a[0])
    return [x + k * (y-x) for x, y in zip(a[1:], b[1:])]


def replay(case, folder, template, pwl, model, env, samples):
    leg, mv, rp, rn = case
    work = folder / f'{leg}_{mv}'
    work.mkdir()
    simulate(work, template.substitute(model=model, dut=DUT, offset=mv/1000, rp=rp, rn=rn, pwl=pwl), env)
    rows = [tuple(map(float, line.split())) for line in (work/'trace.dat').read_text().splitlines()]
    if not rows or any(len(r) != 4 or not all(map(math.isfinite, r)) for r in rows):
        raise ValueError(f'invalid output vectors: {case}')
    times = [r[0] for r in rows]
    if times[-1] < END-1e-9 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError(f'incomplete or non-monotonic transient: {case}')
    p0, n0, _ = interpolate(times, rows, 1/RATE)
    y = []
    clipped = 0
    for i, x in enumerate(samples):
        p, n, source = interpolate(times, rows, START + i/RATE)
        if abs(source - mv/1000 - x) > 1e-9:
            raise ValueError(f'{case}: source did not reach CSV value at sample {i}')
        y.append((p-n) - (p0-n0))
        clipped += min(p, n) <= RAIL_GUARD or max(p, n) >= 3.3-RAIL_GUARD
    played = [r for r in rows if r[0] >= START - 1e-12]
    metric = {'source': leg, 'differential_offset_mV': mv, 'RP_ohm': rp, 'RN_ohm': rn,
              'no_EEG_output_diff_V': p0-n0, 'clipped_samples': clipped,
              'clipped_fraction': clipped/len(samples),
              'outp_range_V': [min(r[1] for r in played), max(r[1] for r in played)],
              'outn_range_V': [min(r[2] for r in played), max(r[2] for r in played)]}
    print(f'Completed {leg}, {mv:+d} mV', flush=True)
    return metric, y


def recovery(folder, model, env):
    # Run the separate synthetic, power-ramped, balanced-source bench unchanged except paths.
    work = folder/'recovery'
    work.mkdir()
    deck = RECOVERY.read_text().replace('/foss/pdks/sky130A/libs.tech/ngspice/sky130.lib.spice',
                                       f'"{model}"').replace('/foss/designs/afe/runs/hiz-size-g/tbci_native_input.spice', f'"{DUT}"')
    log = simulate(work, deck, env)
    metrics = {}
    for key in ('startup_diff', 'positive_response', 'positive_residual', 'negative_response',
                'negative_residual', 'small_signal_response', 'final_rail'):
        match = re.search(rf'^{key}\s*=\s*(\S+)', log, re.M)
        if not match or not math.isfinite(value := float(match[1])):
            raise ValueError(f'missing {key} from offset-step bench')
        metrics[key+'_V'] = value
    return {'bench': str(RECOVERY.relative_to(ROOT)), 'bench_sha256': sha(RECOVERY),
            'conditions': 'Separate synthetic transient: rail and reference ramp; 10 kOhm per source, both polarities. Not the four-second EEG replay.',
            'observation': 'Sampled OUTP-OUTN at 5.9/9.9 ms during applied offsets and at 7.9/11.9 ms, 1.8 ms after the respective ramps back to zero ended. Not a settling-time bound.',
            **metrics}


def rms(x):
    return math.sqrt(fmean(v*v for v in x))


def svg(path, x, results, cal):
    worst, y = max(results, key=lambda pair: pair[0]['fixed_gain_NRMSE_pct'])
    traces = [[v*1e6 for v in x], [v*1e6/cal for v in y]]
    amp = math.ceil(max(abs(v) for trace in traces for v in trace)/50)*50
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="880" height="428" viewBox="0 0 880 428" role="img">',
             '<title>Rev G simulated replay of recorded EEG and gain under electrode offsets</title>',
             '<style>text{font:15px sans-serif;fill:#162e3e}.title{font:bold 20px sans-serif}.small{font:13px sans-serif}</style>',
             '<rect width="880" height="428" fill="white"/>']
    def text(a, b, s, cls='', anchor='start'):
        parts.append(f'<text x="{a}" y="{b}" class="{cls}" text-anchor="{anchor}">{s}</text>')
    def line(x1, y1, x2, y2, color, width=1):
        parts.append(f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{color}" stroke-width="{width}"/>')
    text(12, 26, 'A   Oz waveform  |  input-referred µV', 'title')
    text(12, 49, f'Fixed balanced gain {cal:.3f} V/V; largest-error case: {worst["differential_offset_mV"]:+d} mV, {worst["source"].replace("_high", " +10 kΩ")}.')
    left, right, mid, scale = 68, 849, 141, 69/amp
    for v in (-amp, 0, amp):
        yy = mid-v*scale
        line(left, yy, right, yy, '#ccd6db'); text(left-7, yy+5, str(v), 'small', 'end')
    for i in range(5):
        xx = left+(right-left)*i/4
        line(xx, mid-69, xx, mid+69, '#e0e6e9'); text(xx, 229, str(i)+' s', 'small', 'middle')
    for trace, color, width, dash in zip(traces, ['#162e3e','#c34d10'], [2.4,1.5], ['', 'stroke-dasharray="4 2"']):
        coords = ' '.join(f'{left+(right-left)*i/(4*RATE):.1f},{mid-v*scale:.2f}' for i, v in enumerate(trace))
        parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="{width}" {dash}/>')
    line(78, 250, 108, 250, '#162e3e', 2.4); text(115, 255, 'Original recording')
    line(297, 250, 327, 250, '#c34d10', 2); text(334, 255, 'Simulated output, quiet DC subtracted, divided by fixed gain')
    text(12, 294, 'B   Offset comparison  |  NO input null', 'title')
    for i, header in enumerate(['Input offset', 'Pair baseline¹', 'Gain P-high / N-high', 'Fixed NRMSE P / N']):
        text([32,205,396,653][i], 322, header)
    for j, mv in enumerate((-100,0,100)):
        p, n = [m for m,_ in results if m['source']!='balanced' and m['differential_offset_mV']==mv]
        row = [f'{mv:+d} mV', f'{p["no_EEG_output_diff_V"]*1000:+.1f} mV',
               f'{p["gain_V_per_V"]:.3f} / {n["gain_V_per_V"]:.3f} V/V',
               f'{p["fixed_gain_NRMSE_pct"]:.2f} / {n["fixed_gain_NRMSE_pct"]:.2f} %']
        for xx, s in zip([32,205,396,653],row): text(xx,345+j*22,s)
    text(12, 418, '¹ Quiet OUTP−OUTN, P-high shown. TT, 27 °C, no noise or pads. Data: Schalk / PhysioNet, ODC-By 1.0.', 'small')
    path.write_text('\n'.join(parts+['</svg>','']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    parser.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument('--pdk', type=Path, default=Path(os.environ.get('PDKPATH', '/foss/pdks/sky130A')))
    args = parser.parse_args()
    if args.out.exists(): parser.error(f'output directory exists: {args.out}')
    if args.jobs < 1: parser.error('--jobs must be positive')
    model = (args.pdk/'libs.tech/ngspice/sky130.lib.spice').resolve(strict=True)
    env = dict(os.environ, OMP_NUM_THREADS='1', SPICE_USERINIT_DIR=str(model.parent))
    fixture = json.loads((DATA/'attribution.json').read_text())
    csv_path = DATA/fixture['file']
    if sha(csv_path) != fixture['sha256']: raise ValueError('EEG fixture checksum mismatch')
    with csv_path.open(newline='') as f:
        rows = list(csv.DictReader(f))
    x = [float(r['v_V']) for r in rows]
    if len(rows) != 640 or any(float(r['t_s']) != i/RATE for i,r in enumerate(rows)):
        raise ValueError('expected the 640 original 160 Hz CSV samples')
    pwl = '\n'.join(f'+ {START+i/RATE:.8f} {v:.12g}' for i,v in enumerate(x))
    template_path = DATA/'replay.spice.in'
    template = Template(template_path.read_text())
    with tempfile.TemporaryDirectory(prefix='eeg-replay-') as tmp, ThreadPoolExecutor(args.jobs) as pool:
        folder = Path(tmp)
        tasks = [pool.submit(replay, c, folder, template, pwl, model, env, x) for c in CASES]
        step = pool.submit(recovery, folder, model, env)
        results = [t.result() for t in tasks]
        step_result = step.result()
    xc = [v-fmean_x for fmean_x in [fmean(x)] for v in x]
    sumsq = sum(v*v for v in xc)
    for m,y in results:
        mean_y = fmean(y)
        yc = [v-mean_y for v in y]
        cross = sum(a*b for a,b in zip(xc,yc))
        m['gain_V_per_V'] = cross/sumsq
        m['pearson_r'] = cross/math.sqrt(sumsq*sum(v*v for v in yc))
    cal = results[0][0]['gain_V_per_V']
    for m,y in results:
        error = [b/cal-a for a,b in zip(x,y)]
        m['gain_error_vs_balanced_pct'] = 100*(m['gain_V_per_V']/cal-1)
        m['fixed_gain_input_error_uVrms'] = 1e6*rms(error)
        m['fixed_gain_NRMSE_pct'] = 100*rms(error)/rms(x)
    version = subprocess.check_output(['ngspice','--version'], env=env, text=True)
    sources = args.pdk/'SOURCES'
    report = {'scope': 'Single Rev G Xschem-netlisted DUT, not layout extraction or silicon. No transient noise, pads, ADC, active receiver or electrode interface other than series resistance.',
              'fixture': fixture, 'samples': len(x), 'sample_rate_Hz': RATE,
              'EEG_peak_to_peak_uV': (max(x)-min(x))*1e6, 'EEG_rms_uV': rms(x)*1e6,
              'dut': str(DUT.relative_to(ROOT)), 'dut_sha256': sha(DUT),
              'bench_template_sha256': sha(template_path),
              'ngspice_version': next(s.strip('* ') for s in version.splitlines() if re.search(r'ngspice-\d+',s)),
              'PDK': 'Sky130A', 'PDK_sources': sources.read_text().strip() if sources.is_file() else None,
              'model_library_sha256': sha(model), 'corner': 'tt', 'temperature_C': 27, 'supply_V': 3.3,
              'source_common_mode_V': 1.65, 'reference_sink_uA': 8,
              'load_per_output_to_VCM': '4.915 MOhm parallel 100 fF',
              'method': 'DC operating point with constant electrode offset. Two quiet sample periods, one-period ramp to first CSV value, PWL to last CSV value held to 4 s. Input is differential: VCM +/- (offset + EEG)/2. Compare all 640 original times. No lag fit, smoothing, noise injection or input null.',
              'fixed_calibration_V_per_V': cal,
              'error_definition': 'Subtract separately observed quiet OUTP-OUTN at the same static offset before replay (not an on-chip offset servo). Pearson r and fitted slope use centered vectors. Fixed NRMSE = 100 * rms((OUTP-OUTN-quiet)/G_balanced - CSV)/rms(CSV); all cases share one balanced 0 mV slope. No per-case gain correction.',
              'clipping_definition': 'Count CSV sample instants with either output <= 0.050 V or >= 3.250 V (50 mV rail guard); not a linearity test. Output ranges are extrema of all saved simulator timepoints during the replay, including final hold.',
              'cases': [m for m,_ in results], 'offset_step_recovery': step_result}
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'metrics.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    svg(args.out/'waveform.svg', x, results, cal)
    print(args.out/'metrics.json', args.out/'waveform.svg', sep='\n')


if __name__ == '__main__':
    main()
