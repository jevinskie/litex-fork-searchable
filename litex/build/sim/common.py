import os

from migen import *
from migen.fhdl.specials import Special
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.io import *

# AsyncResetSynchronizer ---------------------------------------------------------------------

class SimAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        self.clock_domains.cd_resync = ClockDomain(reset_less=True)
        self.comb += self.cd_resync.clk.eq(cd.clk)
        rst1 = Signal()
        self.sync.resync += [
            rst1.eq(async_reset),
            cd.rst.eq(async_reset | rst1)
        ]

class SimAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return SimAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

# DDROutput ----------------------------------------------------------------------------------------

class SimDDROutputImpl(Module):
    def __init__(self, o, i1, i2, clk):
        self.specials += Instance("DDR_OUTPUT",
            i_i1  = i1,
            i_i2  = i2,
            o_o   = o,
            i_clk = clk
        )

class SimDDROutput:
    @staticmethod
    def lower(dr):
        return SimDDROutputImpl(dr.o, dr.i1, dr.i2, dr.clk)

# DDRInput -----------------------------------------------------------------------------------------

class SimDDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("DDR_INPUT",
            o_o1  = o1,
            o_o2  = o2,
            i_i   = i,
            i_clk = clk
        )

class SimDDRInput:
    @staticmethod
    def lower(dr):
        return SimDDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Special Overrides --------------------------------------------------------------------------------

sim_special_overrides = {
    AsyncResetSynchronizer : SimAsyncResetSynchronizer,
    DDROutput              : SimDDROutput,
    DDRInput               : SimDDRInput,
}


# Clocking (for non-Verilator simulations)

class SimClocker(Module):
    def __init__(self, clk_sig, clk_freq):
        self.mod_name = f"sim_clocker_{int(clk_freq):_}_hz"
        sig_name = clk_sig.name if clk_sig.name else clk_sig.backtrace[-1][0]
        name = f"sim_clocker_{sig_name}"
        self.specials += Instance(self.mod_name, name=name, o_clk=clk_sig)

    def do_finalize(self):
        super().do_finalize()
        verilog_filename = os.path.join(self.platform.output_dir, "gateware", self.mod_name + ".v")
        with open(verilog_filename, "w") as v:
            v.write("""\
hello
            """)
        