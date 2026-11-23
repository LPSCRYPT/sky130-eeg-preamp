#!/usr/bin/env python3
"""Netlist the editable symbol consumer and exercise its instance against the frozen core."""
from collections import defaultdict
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORE = 'tbci_native_input'
CHAIN = 'tbci_bias_chain'
STRING = 'tbci_bias_return'
# Physical landing nets in public_symbol.sch, keyed by formal name, not position.
LAND = dict(avdd='rail', avss='ret', vcm='mid', iref_sink='bias', vinp='plus_in',
            vinn='minus_in', outp='plus_out', outn='minus_out')
FROZEN = ROOT / f'afe/runs/hiz-size-g/{CORE}.spice'


def require(ok, message):
    if not ok:
        raise SystemExit(f'Wiring check failed: {message}')


def check_hierarchy(lines, origin):
    """Validate both hierarchy boundaries and actual body-tied series paths."""
    def cell(name):
        headers = [i for i, line in enumerate(lines) if line[:2] == ['.subckt', name]]
        require(len(headers) == 1, f'{origin}: missing/duplicate {name}')
        start, = headers
        end = next(i for i in range(start+1, len(lines)) if lines[i][:1] == ['.ends'])
        return lines[start][2:], [r for r in lines[start+1:end] if r and r[0].startswith('x')]

    pins, devices = cell(CORE)
    require(pins == list(LAND), f'{origin}: changed public ABI: {pins}')
    returns = [r[1:-1] for r in devices if r[-1] == CHAIN]
    require(sorted(returns) == [['vinn', 'vcm', 'avss'], ['vinp', 'vcm', 'avss']],
            f'{origin}: expected separate VINP and VINN bias returns')
    for name, model, count in [(CHAIN, STRING, 8), (STRING, 'sky130_fd_pr__res_xhigh_po_0p35', 16)]:
        pins, rows = cell(name)
        require(pins == ['sig', 'vcm', 'avss'] and len(rows) == count, f'{origin}: {name} interface/count')
        edges = defaultdict(list)
        for r in rows:
            require(r[3:5] == ['avss', model] and 'avss' not in r[1:3], f'{origin}: {name}: {r}')
            if name == STRING:
                require({'l=860', 'mult=1'} <= set(r[5:]), f'{origin}: resistor sizing: {r}')
            a, b = r[1:3]
            edges[a].append(b)
            edges[b].append(a)
        node, visited = 'sig', set()
        while node != 'vcm':
            visited.add(node)
            nxt = [n for n in edges[node] if n not in visited]
            require(len(nxt) == 1, f'{origin}: {name}: branch, loop or open at {node}')
            node, = nxt
        require(len(visited) == count, f'{origin}: {name}: path bypasses sections')


def tokens(path):
    return [line.lower().split() for line in path.read_text().splitlines()]


def main():
    model = Path(os.environ['PDK_ROOT']) / 'sky130A/libs.tech/ngspice/sky130.lib.spice'
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        subprocess.run(['xschem', '-q', '-x', '-n', '-s', '--rcfile', ROOT/'xschemrc',
                        '-o', work, ROOT/'afe/benches/public_symbol.sch'], check=True, cwd=ROOT)
        generated = tokens(work/'public_symbol.spice')
        frozen = tokens(FROZEN)
        check_hierarchy(generated, 'consumer hierarchy')
        def core_statements(rows):
            start = next(i for i, row in enumerate(rows) if row[:2] == ['.subckt', CORE])
            return [r for r in rows[start:] if r and not r[0].startswith('*') and r != ['.end']]
        require(core_statements(generated) == core_statements(frozen),
                'editable consumer hierarchy differs electrically from the frozen core')
        header, = (r for r in frozen if r[:2] == ['.subckt', CORE])
        calls = [r for r in generated if r[:1] == ['xdut']]
        require(calls == [['xdut', *(LAND[pin] for pin in header[2:]), CORE]],
                f'actual consumer instance does not match frozen .subckt: {calls}')
        wrapper, = (r for r in generated if r[:2] == ['.subckt', 'public_symbol'])
        require(sorted(wrapper[2:]) == sorted(LAND.values()), f'fixture port mismatch: {wrapper}')
        nets = ['0' if pin == 'ret' else pin for pin in wrapper[2:]]
        deck = f'''Symbol consumer TT power ramp and differential polarity check, no pads or ADC
.lib "{model}" tt
.include "{work/'public_symbol.spice'}"
Xfixture {' '.join(nets)} public_symbol
VDD rail 0 PWL(0 0 1m 3.3)
VCM mid 0 PWL(0 0 1m 1.65)
VSENSE bias sink 0
IREF sink 0 PWL(0 0 1.2m 0 1.3m 8u)
VDIFF diff 0 PWL(0 0 4m 0 4.1m 100m 6m 100m 6.1m 0 8m 0 8.1m -100m 10m -100m)
EP psrc mid diff 0 0.5
EN nsrc mid diff 0 -0.5
VP psrc plus_in 0
VN nsrc minus_in 0
RLP plus_out mid 4.915meg
RLN minus_out mid 4.915meg
CLP plus_out mid 100f
CLN minus_out mid 100f
.temp 27
.options klu method=gear maxord=2 reltol=1e-4 abstol=1e-13 vntol=1e-7
.control
set wr_singlescale
save v(diff) v(plus_out) v(minus_out) i(vdd) i(vsense) i(vp) i(vn) v(bias)
tran 25u 10m 0 25u
wrdata sweep.dat v(diff) v(plus_out,minus_out) i(vdd) i(vsense) i(vp) i(vn) v(bias)
quit
.endc
.end
'''
        (work/'check.spice').write_text(deck)
        subprocess.run(['ngspice', '-b', 'check.spice'], cwd=work, check=True, timeout=120)
        trace = [list(map(float, ln.split())) for ln in (work/'sweep.dat').read_text().splitlines()]
        require(trace and trace[-1][0] >= 0.010 - 1e-10, 'power-ramp transient incomplete')
        rows = []
        for sample, drive in [(0.0059, 0.1), (0.0099, -0.1)]:
            point = min(trace, key=lambda r: abs(r[0]-sample))
            require(abs(point[0]-sample) <= 25e-6, 'missing settled plateau')
            row = point[1:]
            rows.append(row)
            vin, vout, idd, isink, ip, inn, vbias = row
            require(abs(vin-drive) < 1e-7 and vout/vin > 1, f'differential sign/gain: {row}')
            require(-100e-6 < idd < -8e-6 and abs(isink-8e-6) < 1e-9 and 0 < vbias < 3.3,
                    f'rail or sink bias: {row}')
        require(rows[0][4] > rows[1][4] and rows[0][5] < rows[1][5], 'input return current polarity')
        print('PASS: public symbol → Rev G; 2 × 8 × 16 series returns, AVSS bodies; TT offset plateaus')
        print('Vin_diff[V] Vout_diff[V] I(VDD)[A] I(sink sense)[A] I(VINP)[A] I(VINN)[A] V(bias)[V]')
        for row in rows:
            print(' '.join(f'{value:.6g}' for value in row))


if __name__ == '__main__':
    main()
