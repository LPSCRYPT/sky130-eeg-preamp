#!/usr/bin/env python3
"""Bound the effect of attaching example instrument loads directly to the unbuffered core."""
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
model = Path(os.environ['PDK_ROOT']) / 'sky130A/libs.tech/ngspice/sky130.lib.spice'
dut = root / 'afe/runs/hiz-size-g/tbci_native_input.spice'
rows = []
for label, r, c, ref in [('core surrogate to VCM', 4.915e6, 100e-15, 1.65), ('10 Mohm / 15 pF to ground', 10e6, 15e-12, 0), ('1 Mohm / 20 pF to ground', 1e6, 20e-12, 0)]:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / 'test.sp').write_text(f'''Direct readout load sensitivity - matched ports, no pad or instrument noise
.lib {model} tt
.include {dut}
.temp 27
VDD avdd 0 3.3
VCM ref 0 1.65
IBIAS sink 0 8u
Vdiff d 0 dc 0 ac 1
Ep srcp ref d 0 0.5
En srcn ref d 0 -0.5
Rp srcp inp 10k
Rn srcn inn 10k
Xdut avdd 0 ref sink inp inn opout onout tbci_native_input
Vload rtn 0 {ref}
Rlp opout rtn {r}
Rln onout rtn {r}
Clp opout rtn {c}
Cln onout rtn {c}
.control
op
let common=(v(opout)+v(onout))/2
wrdata common.dat common
ac lin 1 10 10
let gain=mag(v(opout)-v(onout))
wrdata gain.dat gain
quit
.endc
.end
''')
        p = subprocess.run(['ngspice', '-b', 'test.sp'], cwd=work, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120, check=True)
        if any(msg in p.stdout.lower() for msg in ('error:', 'aborted', 'fatal', 'timestep too small')):
            raise SystemExit(p.stdout[-3000:])
        cm, gain = (float((work / k).read_text().split()[-1]) for k in ('common.dat', 'gain.dat'))
        if not all(map(math.isfinite, [cm, gain])) or not 0 < cm < 3.3 or gain <= 0:
            raise RuntimeError(f'Invalid operating point or gain for {label}: {cm}, {gain}')
        rows.append(dict(load=label, R_ohm_per_leg=r, C_F_per_leg=c, termination_V=ref, output_common_mode_V=cm, differential_gain_10Hz=gain))
print(json.dumps({'conditions':'TT, 27 C, 3.3 V, ideal 1.65 V and 8 uA, 10 kohm matched sources, zero offset. Linear R/C terminations only, no pad, package, buffer or recorder noise.', 'cases':rows}, indent=2, allow_nan=False))
