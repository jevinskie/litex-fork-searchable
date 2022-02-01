#
# This file is part of LiteX.
#
# Copyright (c) 2018-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2018-2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.cores.clock.common import *
from litex.soc.cores.clock.intel_common import *

# Intel / Arria V ----------------------------------------------------------------------------------

class ArriaVPLL(IntelClocking):
    nclkouts_max   = 18
    n_div_range    = (1, 512+1)
    m_div_range    = (1, 512+1)
    c_div_range    = (1, 512+1)
    clkin_pfd_freq_range = (5e6, 325e6)  # FIXME: use
    vco_freq_range       = (600e6, 1600e6)
    def __init__(self, speedgrade="-3"):
        self.logger = logging.getLogger("ArriaVPLL")
        self.logger.info("Creating ArriaVPLL, {}.".format(colorer("speedgrade {}".format(speedgrade))))
        super().__init__()
        self.clkin_freq_range = {
            "-3": (5e6, 800e6),
            "-4": (5e6, 800e6),
            "-5": (5e6, 750e6),
            "-6": (5e6, 625e6),
        }[speedgrade]
        self.clko_freq_range = {
            "-3": (0e6, 500e6),
            "-4": (0e6, 500e6),
            "-5": (0e6, 500e6),
            "-6": (0e6, 400e6),
        }[speedgrade]
