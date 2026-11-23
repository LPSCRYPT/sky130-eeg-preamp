#!/usr/bin/env python3
"""Plot worst-case retention over the characterized common modes and seven stress conditions."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
rows = []
for rev in ('d', 'e', 'g'):
    records = json.loads((root / f'afe/runs/hiz-stress-{rev}/metrics.json').read_text())['results']
    cells = [(p['incremental_gain_V_per_V'] / r['gain_10Hz_V_per_V'], r, p)
             for r in records for p in r['dc_offset_cases']]
    value = min(x[0] for x in cells) * 100
    rows.append((rev.upper(), value))
svg = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 148" role="img" aria-labelledby="title"><title id="title">Minimum incremental gain retained, percent of each corner’s zero-offset 10 Hz gain</title>',
       '<rect width="640" height="148" fill="white"/><g font-family="sans-serif" font-size="15" fill="#193744">',
       '<text x="8" y="20" font-weight="bold">Minimum incremental gain retained across 63 operating points</text>']
for i, (rev, value) in enumerate(rows):
    y = 37 + 35 * i
    svg.extend([f'<text x="8" y="{y + 15}">Rev {rev}</text>',
                f'<rect x="68" y="{y}" width="490" height="19" fill="#e9eef0"/>',
                f'<rect x="68" y="{y}" width="{4.9*value:.2f}" height="19" fill="{"#156d70" if rev == "G" else "#607689"}"/>',
                f'<text x="573" y="{y + 15}">{value:.1f}%</text>'])
svg.append('</g></svg>')
(root / 'proposal/evidence/headroom.svg').write_text('\n'.join(svg) + '\n')
