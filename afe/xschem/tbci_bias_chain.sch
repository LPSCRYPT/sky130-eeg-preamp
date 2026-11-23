v {xschem version=3.4.5 file_version=1.2
}
G {}
K {}
V {}
S {}
E {}
T {High-impedance DC bias return | eight 16-section poly strings in series} 40 30 0 0 0.4 0.4 {}
T {All bodies to AVSS; 128 physical resistors per input. Include distributed capacitance and area in comparisons.} 40 90 0 0 0.3 0.3 {}
C {tbci_bias_return.sym} 180 220 0 0 {name=xs0}
C {devices/lab_pin.sym} 180 280 0 0 {name=p39 lab=AVSS}
C {devices/iopin.sym} 80 220 0 0 {name=p40 lab=SIG}
N 280 220 400 220 {lab=series0}
C {tbci_bias_return.sym} 500 220 0 0 {name=xs1}
C {devices/lab_pin.sym} 500 280 0 0 {name=p41 lab=AVSS}
N 600 220 720 220 {lab=series1}
C {tbci_bias_return.sym} 820 220 0 0 {name=xs2}
C {devices/lab_pin.sym} 820 280 0 0 {name=p42 lab=AVSS}
N 920 220 1040 220 {lab=series2}
C {tbci_bias_return.sym} 1140 220 0 0 {name=xs3}
C {devices/lab_pin.sym} 1140 280 0 0 {name=p43 lab=AVSS}
C {devices/lab_pin.sym} 1240 220 0 1 {name=p44 lab=MID}
C {tbci_bias_return.sym} 180 440 0 0 {name=xs4}
C {devices/lab_pin.sym} 180 500 0 0 {name=p45 lab=AVSS}
C {devices/lab_pin.sym} 80 440 0 0 {name=p46 lab=MID}
N 280 440 400 440 {lab=series4}
C {tbci_bias_return.sym} 500 440 0 0 {name=xs5}
C {devices/lab_pin.sym} 500 500 0 0 {name=p47 lab=AVSS}
N 600 440 720 440 {lab=series5}
C {tbci_bias_return.sym} 820 440 0 0 {name=xs6}
C {devices/lab_pin.sym} 820 500 0 0 {name=p48 lab=AVSS}
N 920 440 1040 440 {lab=series6}
C {tbci_bias_return.sym} 1140 440 0 0 {name=xs7}
C {devices/lab_pin.sym} 1140 500 0 0 {name=p49 lab=AVSS}
C {devices/iopin.sym} 1240 440 0 0 {name=p50 lab=VCM}
C {devices/iopin.sym} 80 570 0 0 {name=p51 lab=AVSS}
