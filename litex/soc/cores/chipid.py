#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import os

from migen import *
from migen.genlib.misc import WaitTimer
from litex.soc.interconnect.csr import *


class AlteraChipID(Module, AutoCSR):
    def __new__(cls, *args, **kwargs):
        print("newing AlteraChipID")
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, primitive):
        print(f"AlteraChipID: prim: {primitive}")
        self.chip_id  = CSRStatus(64, read_only=True)
        self.valid    = CSRStatus(read_only=True)
        regout        = Signal()
        shiftnld      = Signal()
        done          = Signal()

        n_cycles      = 65
        count         = Signal(bits_for(n_cycles), reset=n_cycles)

        self.comb += [
            done.eq(count == 0),
            self.valid.status.eq(done),
            # must pulse shiftnld low at least one cycle
            shiftnld.eq(~done & (count != count.reset))
        ]

        self.sync += [
            If(~done,
                count.eq(count - 1)
            ),
            # shift in the chip ID
            If(shiftnld,
                self.chip_id.status.eq(Cat(self.chip_id.status[1:], regout))
            )
        ]

        self.specials += Instance(primitive, "chipid",
            i_clk      = ClockSignal("sys"),
            i_shiftnld = shiftnld,
            o_regout   = regout,
        )

    @staticmethod
    def get_primitive(device):
        prim_dict = {
            # Primitive Name                Device (startswith)
            "arriavgz_chipidblock"        : ["5agz"],
            "arriav_chipidblock"          : ["5agt", "5agx", "5ast", "5asx"],
            "cyclonev_chipidblock"        : ["5c"],
            "fiftyfivenm_chipidblock"     : ["10m"],
            # TODO
            "stratixv_chipidblock"        : [],
        }
        for prim, prim_devs in prim_dict.items():
            for prim_dev in prim_devs:
                if device.lower().startswith(prim_dev):
                    return prim
        return None


class ChipID(Module):
    def __new__(cls, platform):
        alt_prim = AlteraChipID.get_primitive(platform.device)
        print(f"altprint: {alt_prim}")
        if alt_prim:
            print("super newing")
            obj = AlteraChipID.__new__(AlteraChipID)
            obj.__init__(alt_prim)
            return obj
        else:
            raise NotImplementedError

    def __init__(self, *args, **kwargs):
        print("ChipID __init__")
        super().__init__(*args, **kwargs)


# For verification, delete before merge
class AlteraChipIDIP(Module, AutoCSR):
    def __init__(self, platform):
        self.chip_id = CSRStatus(64, read_only=True)
        self.valid   = CSRStatus(read_only=True)

        self.specials += Instance("altchip_id", "chipid",
            i_clkin         = ClockSignal("sys"),
            i_reset         = ResetSignal("sys"),
            o_chip_id       = self.chip_id.status,
            o_data_valid    = self.valid.status,
            p_DEVICE_FAMILY = "MAX 10"
        )

        platform.add_source(os.path.join(
            platform.toolchain.ip_dir, "altera", "altchip_id", "source", "altchip_id.v"
        ))
