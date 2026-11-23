#!/bin/sh
# Build from Markdown, figures, and CSS without personal PDF metadata or local file links.
set -eu
cd "$(dirname "$0")/../proposal"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
pandoc --standalone --embed-resources --resource-path=. -M 'pagetitle=Sky130 EEG preamplifier with electrode-offset headroom' -M lang=en --css=print.css --lua-filter=../tools/print-links.lua --to=html5 proposal.md evidence.md measurement.md -o "$tmp/proposal.html"
weasyprint "$tmp/proposal.html" "$tmp/proposal.pdf"
mv "$tmp/proposal.pdf" chipalooza-4-eeg-preamp.pdf
