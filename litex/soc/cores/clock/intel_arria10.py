#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen.fhdl.utils import InstancePlainParameters
from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / Arria 10 ---------------------------------------------------------------------------------

class Arria10FPLL(IntelClocking):
    nclkouts_max   = 4
    n_div_range    = (1, 32+1)
    m_div_range    = (8, 127+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range = (30e6, 700e6)  # FIXME: use
    clkin_freq_range     = (30e6, 800e6)
    clko_freq_range      = (0e6, 644e6)
    vco_freq_range       = (6_000e6, 14_025e6)

    def __init__(self):
        self.logger = logging.getLogger("Arria10FPLL")
        self.logger.info("Creating Arria10FPLL.")
        super().__init__()

    def do_finalize(self):
        assert hasattr(self, "clkin")
        config = self.compute_config()
        clks = Signal(self.nclkouts)
        self.params.update(
            p_reference_clock_frequency = int(1e12/self.clkin_freq),
            p_operation_mode            = "normal",
            i_refclk                    = self.clkin,
            o_outclk                    = clks,
            i_rst                       = ~self.locked,
            o_locked                    = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            clk_phase_ps = int((1e12/config[f"clk{n}_freq"])*config[f"clk{n}_phase"]/360)
            self.params[f"p_output_clock_frequency{n}"] = config[f"clk{n}_freq"]
            self.params[f"p_phase_shift{n}"] = clk_phase_ps
            self.params[f"p_clock_name_{n}"] = f"dummyname2{n}"
            self.comb += clk.eq(clks[n])
        self.specials += InstancePlainParameters("altera_pll", **self.params)


class Arria10IOPLL(IntelClocking):
    nclkouts_max   = 8
    n_div_range    = (1, 80+1)
    m_div_range    = (4, 160+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range = (10e6, 325e6)  # FIXME: use
    clko_freq_range      = (0e6, 644e6)

    def __init__(self, speedgrade="-3"):
        self.logger = logging.getLogger("Arria10IOPLL")
        self.logger.info("Creating Arria10IOPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        super().__init__()
        self.vco_freq_range = {
            "-1" : (600e6, 1600e6),
            "-2" : (600e6, 1434e6),
            "-3" : (600e6, 1250e6),
        }[speedgrade]
        self.clkin_freq_range = {
            "-1" : (10e6, 800e6),
            "-2" : (10e6, 700e6),
            "-3" : (10e6, 650e6),
        }[speedgrade]

    def do_finalize(self):
        assert hasattr(self, "clkin")
        config = self.compute_config()
        clks = Signal(self.nclkouts)
        self.params.update(
            p_clock_to_compensate       = 0,
            p_reference_clock_frequency = int(1e12/self.clkin_freq),
            p_operation_mode            = "normal",
            i_refclk                    = self.clkin,
            o_outclk                    = clks,
            i_rst                       = ~self.locked,
            o_locked                    = self.locked,
        )
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            clk_phase_ps = int((1e12/config[f"clk{n}_freq"])*config[f"clk{n}_phase"]/360)
            self.params[f"p_output_clock_frequency{n}"] = config[f"clk{n}_freq"]
            self.params[f"p_phase_shift{n}"] = clk_phase_ps
            self.params[f"p_clock_name_{n}"] = f"dummyname{n}"
            self.comb += clk.eq(clks[n])
        self.specials += InstancePlainParameters("altera_iopll", **self.params)
