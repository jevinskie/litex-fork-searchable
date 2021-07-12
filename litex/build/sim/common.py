#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# Common AsyncResetSynchronizer --------------------------------------------------------------------

class SimAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst_meta = Signal()
        self.specials += [
            Instance("GenericDFF",
                i_d    = 0,
                i_clk  = cd.clk,
                i_r    = 0,
                i_s    = async_reset,
                o_q    = rst_meta
            ),
            Instance("GenericDFF",
                i_d    = rst_meta,
                i_clk  = cd.clk,
                i_r    = 0,
                i_s    = async_reset,
                o_q    = cd.rst
            )
        ]


class SimAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return SimAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

class CocotbVCDDumperSpecial(Special):
    @staticmethod
    def emit_verilog(instance, ns, add_data_file):
        r = """
// the "macro" to dump signals
`ifdef COCOTB_SIM_DUMP_VCD_VERILOG
initial begin
  $dumpfile (`COCOTB_SIM_DUMP_VCD_VERILOG);
  $dumpvars (0, `COCOTB_SIM_DUMP_VCD_VERILOG_TOPLEVEL);
  #1;
end
"""
        return r

    @staticmethod
    def lower(dr):
        pass


# Special Overrides --------------------------------------------------------------------------------

sim_special_overrides = {
    AsyncResetSynchronizer: SimAsyncResetSynchronizer,
}
