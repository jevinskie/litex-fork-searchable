#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from litex.build.generic_platform import *
from litex.build.altera import common, quartus

# AlteraPlatform -----------------------------------------------------------------------------------

class AlteraPlatform(GenericPlatform):
    bitstream_ext = ".sof"
    create_rbf    = True

    def __init__(self, *args, toolchain="quartus", **kwargs):
        GenericPlatform.__init__(self, *args, **kwargs)
        self.ips = set()
        if toolchain == "quartus":
            self.toolchain = quartus.AlteraQuartusToolchain()
        else:
            raise ValueError("Unknown toolchain")

    def add_ip(self, filename):
        self.ips.add((os.path.abspath(filename)))

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.altera_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_period_constraint(self, clk, period):
        if clk is None: return
        if hasattr(clk, "p"):
            clk = clk.p
        self.toolchain.add_period_constraint(self, clk, period)

    def add_false_path_constraint(self, from_, to):
        if hasattr(from_, "p"):
            from_ = from_.p
        if hasattr(to, "p"):
            to = to.p
        self.toolchain.add_false_path_constraint(self, from_, to)

    def add_reserved_jtag_decls(self):
        # self.add_extension([
        #     ("altera_jtag_reserved", 0,
        #         Subsignal("altera_reserved_tms", Pins("Y7"), IOStandard("2.5 V")),
        #         Subsignal("altera_reserved_tck", Pins("Y8"), IOStandard("2.5 V")),
        #         Subsignal("altera_reserved_tdi", Pins("AB2"), IOStandard("2.5 V")),
        #         Subsignal("altera_reserved_tdo", Pins("AB3"), IOStandard("2.5 V")),
        #     ),
        # ])
        # self.add_extension([
        #     Signal(name="altera_reserved_tms", reset=None, reset_less=True),
        #     Signal(name="altera_reserved_tck", reset=None, reset_less=True),
        #     Signal(name="altera_reserved_tdi", reset=None, reset_less=True),
        #     Signal(name="altera_reserved_tdo", reset=None, reset_less=True),
        # ])
        self.add_extension([
            ("altera_reserved_tms", 0, Pins(1)),
            ("altera_reserved_tck", 0, Pins(1)),
            ("altera_reserved_tdi", 0, Pins(1)),
            ("altera_reserved_tdo", 0, Pins(1)),
        ])
