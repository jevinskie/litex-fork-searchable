#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.interconnect.csr import *
from litex.soc.integration.soc import colorer

logging.basicConfig(level=logging.INFO)

class AlteraChipID(Module, AutoCSR):
    def __init__(self, primitive):
        self.chip_id  = CSRStatus(64, read_only=True)
        self.valid    = CSRStatus(read_only=True)
        regout        = Signal()
        shiftnld      = Signal()
        done          = Signal()

        if ClockFrequency() > 100e6:
            logging.warn(f"Altera Chip ID block should be clocked {colorer('<= 100 MHz')}, not " +
                colorer(f"{ClockFrequency()/1e6:.0f} MHz")
            )

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
            i_clk      = ClockSignal(),
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


def get_chipid_module(platform):
    alt_prim = AlteraChipID.get_primitive(platform.device)
    if alt_prim:
        return AlteraChipID(alt_prim)
    raise NotImplementedError


# For verification, delete before merge
class AlteraChipIDIP(Module, AutoCSR):
    def __init__(self, platform):
        self.chip_id = CSRStatus(64, read_only=True)
        self.valid   = CSRStatus(read_only=True)

        self.specials += Instance("altchip_id", "chipid",
            i_clkin         = ClockSignal(),
            i_reset         = ResetSignal(),
            o_chip_id       = self.chip_id.status,
            o_data_valid    = self.valid.status,
            p_DEVICE_FAMILY = "MAX 10"
        )

        platform.add_source(os.path.join(
            platform.toolchain.ip_dir, "altera", "altchip_id", "source", "altchip_id.v"
        ))
