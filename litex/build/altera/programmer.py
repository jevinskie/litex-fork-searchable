#
# This file is part of LiteX.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build.generic_programmer import GenericProgrammer

# USBBlaster ---------------------------------------------------------------------------------------

class USBBlaster(GenericProgrammer):
    needs_bitreverse = False

    def __init__(self, cable_name="USB-Blaster", device_id=1, mode="jtag"):
        self.cable_name = cable_name
        self.device_id  = device_id
        self.mode       = mode

    def load_bitstream(self, bitstream_file, cable_suffix=""):
        args = ["quartus_pgm",
            "-m", self.mode,
             "-c", "{}{}".format(self.cable_name, cable_suffix),
             "-o", "p;{}@{}".format(bitstream_file, self.device_id)
        ]
        print(f"args: {' '.join(args)}")
        self.call(args)
