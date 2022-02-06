#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

"""Avalon support for LiteX"""

from migen import *
from migen.genlib.record import Record, set_layout_parameters

from litex.soc.interconnect import stream

# Avalon-ST to/from native LiteX's stream ----------------------------------------------------------

# In native LiteX's streams, ready signal has no latency (similar to AXI). In Avalon-ST streams the
# ready signal has a latency: If ready is asserted on cycle n, then cycle n + latency is a "ready"
# in the LiteX/AXI's sense) cycle. This means that:
# - when converting to Avalon-ST, we need to add this latency on datas.
# - when converting from Avalon-ST, we need to make sure we are able to store datas for "latency"
# cycles after ready deassertion on the native interface.

class Native2AvalonST(Module):
    """Native LiteX's stream to Avalon-ST stream"""
    def __init__(self, layout, latency=2):
        self.sink   = sink   = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        _from = sink
        for n in range(latency):
            _to = stream.Endpoint(layout)
            self.sync += _from.connect(_to, omit={"ready"})
            if n == 0:
                self.sync += _to.valid.eq(sink.valid & source.ready)
            _from = _to
        self.comb += _to.connect(source, omit={"ready"})
        self.comb += sink.ready.eq(source.ready)


class AvalonST2Native(Module):
    """Avalon-ST Stream to native LiteX's stream"""
    def __init__(self, layout, latency=2):
        self.sink   = sink   = stream.Endpoint(layout)
        self.source = source = stream.Endpoint(layout)

        # # #

        buf = stream.SyncFIFO(layout, latency)
        self.submodules += buf
        self.comb += sink.connect(buf.sink, omit={"ready"})
        self.comb += sink.ready.eq(source.ready)
        self.comb += buf.source.connect(source)

# Avalon-MM Definition -----------------------------------------------------------------------------

_avmm_layout = [
    ("address",     "adr_width",  DIR_M_TO_S),
    ("writedata",   "data_width", DIR_M_TO_S),
    ("readdata",    "data_width", DIR_S_TO_M),
    ("byteenable",  "sel_width",  DIR_M_TO_S),
    ("write",       1,            DIR_M_TO_S),
    ("read",        1,            DIR_M_TO_S),
    ("chipselect",  1,            DIR_M_TO_S),
    ("waitrequest", 1,            DIR_S_TO_M),
    ("response",    2,            DIR_S_TO_M),
]

class AvalonMMInterface(Record):
    def __init__(self, data_width=32, adr_width=30):
        self.data_width    = data_width
        self.adr_width = adr_width
        assert data_width % 8 == 0
        Record.__init__(self, set_layout_parameters(_avmm_layout,
            adr_width  = adr_width,
            data_width = data_width,
            sel_width  = data_width//8))
        self.address.reset_less    = True
        self.writedata.reset_less  = True
        self.readdata.reset_less   = True
        self.byteenable.reset_less = True
        self.response.reset_less   = True


class AvalonMM2Wishbone(Module):
    """Avalon-MM to Wishbone"""
    def __init__(self, avalon_mm, wishbone):
        av = avalon_mm
        wb = wishbone
        wishbone_adr_shift = log2_int(av.data_width // 8)
        assert av.data_width == wb.data_width
        assert av.adr_width == wb.adr_width + wishbone_adr_shift

        self.comb += [
            av.address.eq(wb.adr),
            av.writedata.eq(wb.dat_w),
            wb.dat_r.eq(av.readdata),
            av.byteenable.eq(wb.sel),
            av.write.eq(wb.cyc & wb.we),
            av.read.eq(wb.cyc & ~wb.we),
            av.chipselect.eq(wb.stb),
            wb.ack.eq(~av.waitrequest),
            wb.err.eq(av.response != 0),
        ]
