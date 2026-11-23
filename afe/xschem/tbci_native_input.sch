v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
T {Native NMOS differential preamp | alternative to the headroom-limited PMOS input pair} 40 10 0 0 0.4 0.4 {}
T {8 uA external reference sink; PMOS copies the reference into a low-side NMOS mirror. Native input bodies to AVSS.} 40 60 0 0 0.3 0.3 {}
T {128-section DC bias returns per input} 35 360 0 0 0.3 0.3 {}
T {Bias mirror} 315 110 0 0 0.3 0.3 {}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 280 230 0 0 {name=MREF W=80 L=3 nf=8 mult=1 ad=11.6 as=14.5 pd=82.32 ps=102.9 nrd=0.0036249999999999998 nrs=0.0036249999999999998 sa=0 sb=0 sd=0 model=pfet_g5v0d10v5 spiceprefix=X}
N 300 200 300 160 {lab=AVDD}
N 300 200 300 230 {lab=AVDD}
C {devices/lab_pin.sym} 300 160 0 0 {name=p52 lab=AVDD}
C {devices/lab_pin.sym} 260 230 0 0 {name=p53 lab=IREF_SINK}
N 300 260 300 300 {lab=IREF_SINK}
C {devices/iopin.sym} 300 300 0 0 {name=p54 lab=IREF_SINK}
C {sky130_fd_pr/pfet_g5v0d10v5.sym} 515 230 0 0 {name=MCPY W=80 L=3 nf=8 mult=1 ad=11.6 as=14.5 pd=82.32 ps=102.9 nrd=0.0036249999999999998 nrs=0.0036249999999999998 sa=0 sb=0 sd=0 model=pfet_g5v0d10v5 spiceprefix=X}
N 535 200 535 160 {lab=AVDD}
N 535 200 535 230 {lab=AVDD}
C {devices/lab_pin.sym} 535 160 0 0 {name=p55 lab=AVDD}
C {devices/lab_pin.sym} 495 230 0 0 {name=p56 lab=IREF_SINK}
N 535 260 535 300 {lab=NBIAS}
C {devices/lab_pin.sym} 535 300 0 0 {name=p57 lab=NBIAS}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 350 760 0 0 {name=MNREF W=80 L=3 nf=8 mult=1 ad=11.6 as=14.5 pd=82.32 ps=102.9 nrd=0.0036249999999999998 nrs=0.0036249999999999998 sa=0 sb=0 sd=0 model=nfet_g5v0d10v5 spiceprefix=X}
C {sky130_fd_pr/nfet_g5v0d10v5.sym} 890 760 0 0 {name=MNTAIL W=320 L=3 nf=32 mult=1 ad=46.4 as=49.3 pd=329.28 ps=349.86 nrd=0.0009062499999999999 nrs=0.0009062499999999999 sa=0 sb=0 sd=0 model=nfet_g5v0d10v5 spiceprefix=X}
C {devices/lab_pin.sym} 330 760 0 0 {name=p58 lab=NBIAS}
C {devices/lab_pin.sym} 870 760 0 0 {name=p59 lab=NBIAS}
N 370 730 370 690 {lab=NBIAS}
C {devices/lab_pin.sym} 370 690 0 0 {name=p60 lab=NBIAS}
N 370 760 370 790 {lab=AVSS}
N 910 760 910 790 {lab=AVSS}
N 370 790 370 830 {lab=AVSS}
N 910 790 910 830 {lab=AVSS}
N 370 830 650 830 {lab=AVSS}
N 650 830 910 830 {lab=AVSS}
C {devices/iopin.sym} 650 830 0 0 {name=p61 lab=AVSS}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} 760 240 0 0 {name=RLOAD0 L=24.4 mult=1 model=res_xhigh_po_1p41 spiceprefix=X}
C {devices/lab_pin.sym} 740 240 0 0 {name=p62 lab=AVSS}
N 760 210 760 170 {lab=AVDD}
N 760 270 760 390 {lab=OUTN}
N 760 390 830 390 {lab=OUTN}
C {devices/opin.sym} 830 390 0 0 {name=p63 lab=OUTN}
N 760 390 760 450 {lab=OUTN}
C {sky130_fd_pr/nfet_05v0_nvt.sym} 740 480 0 0 {name=MIN0 W=1280 L=4 nf=128 mult=1 ad=185.6 as=188.5 pd=1317.12 ps=1337.7 nrd=0.00022656249999999998 nrs=0.00022656249999999998 sa=0 sb=0 sd=0 model=nfet_05v0_nvt spiceprefix=X}
N 760 480 825 480 {lab=AVSS}
C {devices/lab_pin.sym} 825 480 0 1 {name=p64 lab=AVSS}
N 720 480 650 480 {lab=VINP}
C {devices/ipin.sym} 650 480 0 0 {name=p65 lab=VINP}
N 760 510 760 550 {lab=S0}
C {sky130_fd_pr/res_high_po_2p85.sym} 760 580 0 0 {name=RDEG0 L=45.55 mult=1 model=res_high_po_2p85 spiceprefix=X}
C {devices/lab_pin.sym} 740 580 0 0 {name=p66 lab=AVSS}
N 760 610 760 650 {lab=TAIL}
C {tbci_bias_chain.sym} 155 460 0 0 {name=xreturn0}
C {devices/lab_pin.sym} 55 460 0 0 {name=p67 lab=VINP}
C {devices/lab_pin.sym} 255 460 0 1 {name=p68 lab=VCM}
C {devices/lab_pin.sym} 155 520 0 0 {name=p69 lab=AVSS}
C {sky130_fd_pr/res_xhigh_po_1p41.sym} 1060 240 0 0 {name=RLOAD1 L=24.4 mult=1 model=res_xhigh_po_1p41 spiceprefix=X}
C {devices/lab_pin.sym} 1040 240 0 0 {name=p70 lab=AVSS}
N 1060 210 1060 170 {lab=AVDD}
N 1060 270 1060 390 {lab=OUTP}
N 1060 390 1130 390 {lab=OUTP}
C {devices/opin.sym} 1130 390 0 0 {name=p71 lab=OUTP}
N 1060 390 1060 450 {lab=OUTP}
C {sky130_fd_pr/nfet_05v0_nvt.sym} 1040 480 0 0 {name=MIN1 W=1280 L=4 nf=128 mult=1 ad=185.6 as=188.5 pd=1317.12 ps=1337.7 nrd=0.00022656249999999998 nrs=0.00022656249999999998 sa=0 sb=0 sd=0 model=nfet_05v0_nvt spiceprefix=X}
N 1060 480 1125 480 {lab=AVSS}
C {devices/lab_pin.sym} 1125 480 0 1 {name=p72 lab=AVSS}
N 1020 480 950 480 {lab=VINN}
C {devices/ipin.sym} 950 480 0 0 {name=p73 lab=VINN}
N 1060 510 1060 550 {lab=S1}
C {sky130_fd_pr/res_high_po_2p85.sym} 1060 580 0 0 {name=RDEG1 L=45.55 mult=1 model=res_high_po_2p85 spiceprefix=X}
C {devices/lab_pin.sym} 1040 580 0 0 {name=p74 lab=AVSS}
N 1060 610 1060 650 {lab=TAIL}
C {tbci_bias_chain.sym} 155 605 0 0 {name=xreturn1}
C {devices/lab_pin.sym} 55 605 0 0 {name=p75 lab=VINN}
C {devices/lab_pin.sym} 255 605 0 1 {name=p76 lab=VCM}
C {devices/lab_pin.sym} 155 665 0 0 {name=p77 lab=AVSS}
N 760 170 910 170 {lab=AVDD}
N 910 170 1060 170 {lab=AVDD}
C {devices/iopin.sym} 910 170 0 0 {name=p78 lab=AVDD}
N 760 650 910 650 {lab=TAIL}
N 910 650 1060 650 {lab=TAIL}
N 910 650 910 730 {lab=TAIL}
C {devices/ipin.sym} 50 830 0 0 {name=p79 lab=VCM}
T {Differential drain output, not an ADC driver. Synthetic bench only; no DC servo, protection or sampling.} 40 900 0 0 0.3 0.3 {}
