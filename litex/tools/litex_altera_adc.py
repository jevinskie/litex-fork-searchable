#!/usr/bin/env python3

import argparse
import time

from litex import RemoteClient

try:
    from rich import print
except ImportError:
    pass

def main(args):
    bus = RemoteClient()
    bus.open()

    bus.regs.adc_tsen.write(1)

    for i in range(2**5):
        bus.regs.adc_chsel.write(i)
        bus.regs.adc_soc.write(1)
        time.sleep(0.001)
        bus.regs.adc_soc.write(0)
        print(f"adc channel {i} {bus.regs.adc_dout.read()}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", action="store_true", help="Dump Altera ADC registers.")
    args = parser.parse_args()
    main(args)
