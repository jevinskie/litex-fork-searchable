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
    def __init__(self):
        self.shiftnld = CSRStorage()
        self.regout   = CSRStatus()
        self.chip_id  = CSRStatus(64)
        self.valid    = CSRStatus()



        self.specials += Instance("fiftyfivenm_chipidblock", "chipid",
            i_clk      = ClockSignal("sys"),
            i_shiftnld = self.shiftnld.storage,
            o_regout   = self.regout.status,
        )

# DELETE BEFORE MERGE
class AlteraChipIDIP(Module, AutoCSR):
    def __init__(self, platform):
        self.reset = CSRStorage()
        self.chip_id = CSRStatus(64)
        self.valid   = CSRStatus()

        self.specials += Instance("altchip_id", "chipid",
            i_clkin      = ClockSignal("sys"),
            i_reset      = self.reset.storage,
            o_data_valid = self.valid.status,
            o_chip_id    = self.chip_id.status,
            p_DEVICE_FAMILY = "MAX 10"
        )

        platform.add_source(os.path.join(
            platform.toolchain.ip_dir, "altera", "altchip_id", "source", "altchip_id.v"
        ))
