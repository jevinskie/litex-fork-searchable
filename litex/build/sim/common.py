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
        clk1_sel_meta = Signal(name_override=f'acm_cd1_{cd_1.name}_sel_meta')
        clk1_en = Signal(name_override=f'acm_cd1_{cd_1.name}_en')
        clk1_dis_meta = Signal(name_override=f'acm_cd1_{cd_1.name}_dis_meta')
        clk1_dis = Signal(name_override=f'acm_cd1_{cd_1.name}_dis')

        clk0_sel_meta = Signal(name_override=f'acm_cd0_{cd_0.name}_sel_meta')
        clk0_en = Signal(name_override=f'acm_cd0_{cd_0.name}_en')
        clk0_dis_meta = Signal(name_override=f'acm_cd0_{cd_0.name}_dis_meta')
        clk0_dis = Signal(name_override=f'acm_cd0_{cd_0.name}_dis')

        self.specials += [
            # Synchronizers
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_ff0',
                i_d    = sel & ~clk0_en,
                i_clk  = cd_1.clk,
                i_r    = clk1_dis,
                i_s    = 0,
                o_q    = clk1_sel_meta
            ),
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_ff1',
                i_d    = clk1_sel_meta,
                i_clk  = ~cd_1.clk,
                i_r    = clk1_dis,
                i_s    = 0,
                o_q    = clk1_en
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_ff0',
                i_d    = ~sel & ~clk1_en,
                i_clk  = cd_0.clk,
                i_r    = clk0_dis,
                i_s    = 0,
                o_q    = clk0_sel_meta
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_ff1',
                i_d    = clk0_sel_meta,
                i_clk  = ~cd_0.clk,
                i_r    = clk0_dis,
                i_s    = 0,
                o_q    = clk0_en
            ),

            # Timers
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_tmr_ff0',
                i_d    = ~sel,
                i_clk  = cd_0.clk,
                i_r    = cd_1.clk,
                i_s    = 0,
                o_q    = clk1_dis_meta
            ),
            Instance("GenericDFF", name=f'acm_cd1_{cd_1.name}_tmr_ff1',
                i_d    = clk1_dis_meta,
                i_clk  = cd_0.clk,
                i_r    = cd_1.clk,
                i_s    = 0,
                o_q    = clk1_dis
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_tmr_ff0',
                i_d    = sel,
                i_clk  = cd_1.clk,
                i_r    = cd_0.clk,
                i_s    = 0,
                o_q    = clk0_dis_meta
            ),
            Instance("GenericDFF", name=f'acm_cd0_{cd_0.name}_tmr_ff1',
                i_d    = clk0_dis_meta,
                i_clk  = cd_1.clk,
                i_r    = cd_0.clk,
                i_s    = 0,
                o_q    = clk0_dis
            ),
        ]

        self.comb += cd_out.clk.eq((cd_1.clk & clk1_en) | (cd_0.clk & clk0_en))


class SimAsyncClockMux:
    @staticmethod
    def lower(dr):
        return SimAsyncClockMuxImpl(dr.cd_0, dr.cd_1, dr.cd_out, dr.sel)


# Common AsyncResetSynchronizer --------------------------------------------------------------------

class SimAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        if not hasattr(async_reset, "attr"):
            i, async_reset = async_reset, Signal(name_override=f'ars_cd_{cd.name}_async_reset')
            self.comb += async_reset.eq(i)
        rst_meta = Signal(name_override=f'ars_cd_{cd.name}_rst_meta')
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
