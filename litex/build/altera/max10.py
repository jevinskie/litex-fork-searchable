#
# This file is part of LiteX.
#
# Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# Copyright (c) 2021 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.module import Module
from migen.fhdl.specials import Instance

from litex.build.io import *


# Common DDROutput -------------------------------------------------------------------------------

class Max10DDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("altera_gpio_lite",
            name = "ddr_in",
            p_PIN_TYPE      = "output",
            p_SIZE          = 1,
            p_REGISTER_MODE = "ddr",
            p_USE_ADVANCED_DDR_FEATURES = "true",
            i_outclock = clk,
            i_din = Cat(i2, i1),
            o_pad_out  = o,
        )

class Max10DDROutput:
    @staticmethod
    def lower(dr):
        return Max10DDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)

# Common DDRInput --------------------------------------------------------------------------------

class Max10DDRInputImpl(Module):
    def __init__(self, i, o1, o2, clk):
        self.specials += Instance("altera_gpio_lite",
            name = "ddr_out",
            p_PIN_TYPE      = "input",
            p_SIZE          = 1,
            p_REGISTER_MODE = "ddr",
            p_USE_ADVANCED_DDR_FEATURES = "true",
            i_inclock = clk,
            i_pad_in = i,
            o_dout = Cat(o2, o1),
        )

class Max10DDRInput:
    @staticmethod
    def lower(dr):
        return Max10DDRInputImpl(dr.i, dr.o1, dr.o2, dr.clk)

# Common SDROutput -------------------------------------------------------------------------------

class Max10DSROutput:
    @staticmethod
    def lower(dr):
        return Max10DDROutputImpl(dr.i, dr.i, dr.o, dr.clk)

# Common SDRInput --------------------------------------------------------------------------------

class Max10SDRInput:
    @staticmethod
    def lower(dr):
        return Max10DDRInputImpl(dr.i, dr.o, Signal(), dr.clk)

# Special Overrides ------------------------------------------------------------------------------

max10_special_overrides = {
    DDROutput:              Max10DDROutput,
    DDRInput:               Max10DDRInput,
    SDROutput:              Max10DSROutput,
    SDRInput:               Max10SDRInput,
}
