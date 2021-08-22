#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance
from migen.genlib.cdc import AsyncClockMux
from migen.genlib.resetsync import AsyncResetSynchronizer, AsyncResetSingleStageSynchronizer

from litex.build.io import *


class SimAsyncClockMuxImpl(Module):
    def __init__(self, cd_0: ClockDomain, cd_1: ClockDomain, cd_out: ClockDomain, sel: Signal):
        clk1_sel_meta = Signal()
        clk1_ff2_q = Signal()

        clk0_sel_meta = Signal()
        clk0_ff2_q = Signal()

        self.specials += [
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_ff0',
                i_d    = sel & ~clk0_ff2_q,
                i_clk  = cd_1.clk,
                i_r    = 0,
                i_s    = 0,
                o_q    = clk1_sel_meta
            ),
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_ff1',
                i_d    = clk1_sel_meta,
                i_clk  = ~cd_1.clk,
                i_r    = 0,
                i_s    = 0,
                o_q    = clk1_ff2_q
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_ff0',
                i_d    = ~sel & ~clk1_ff2_q,
                i_clk  = cd_0.clk,
                i_r    = 0,
                i_s    = 0,
                o_q    = clk0_sel_meta
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_ff1',
                i_d    = clk0_sel_meta,
                i_clk  = ~cd_0.clk,
                i_r    = 0,
                i_s    = 0,
                o_q    = clk0_ff2_q
            )
        ]

        self.comb += cd_out.clk.eq((cd_1.clk & clk1_ff2_q) | (cd_0.clk & clk0_ff2_q))


class SimAsyncClockMux:
    @staticmethod
    def lower(dr):
        return SimAsyncClockMuxImpl(dr.cd_0, dr.cd_1, dr.cd_out, dr.sel)


# Common AsyncResetSynchronizer --------------------------------------------------------------------

class SimAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst_meta = Signal()
        self.specials += [
            Instance("GenericDFF", name=f'ars_cd_{cd.name}_ff0',
                i_d    = 0,
                i_clk  = cd.clk,
                i_r    = 0,
                i_s    = async_reset,
                o_q    = rst_meta
            ),
            Instance("GenericDFF", name=f'ars_cd_{cd.name}_ff1',
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


class SimAsyncResetSingleStageSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        self.specials += [
            Instance("GenericDFF", name=f'arsss_cd_{cd.name}_ff',
                i_d    = 0,
                i_clk  = cd.clk,
                i_r    = 0,
                i_s    = async_reset,
                o_q    = cd.rst
            ),
        ]


class SimAsyncResetSingleStageSynchronizer:
    @staticmethod
    def lower(dr):
        return SimAsyncResetSingleStageSynchronizerImpl(dr.cd, dr.async_reset)


class CocotbVCDDumperSpecial(Special):
    def __init__(self):
        super().__init__()
        self.priority = 100

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
`endif

"""
        return r

    @staticmethod
    def lower(dr):
        pass


# Special Overrides --------------------------------------------------------------------------------

sim_special_overrides = {
    AsyncClockMux: SimAsyncClockMux,
    AsyncResetSynchronizer: SimAsyncResetSynchronizer,
    AsyncResetSingleStageSynchronizer: SimAsyncResetSingleStageSynchronizer,
}
