#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.record import Record
from migen.fhdl.module import Module
from migen.fhdl.structure import Signal, Cat

def get_signals(obj, recurse=False):
    signals = set()

    def add_obj(obj):
        if isinstance(obj, Signal):
            signals.add(obj)
        elif isinstance(obj, Record):
            for robj in obj.flatten():
                if isinstance(robj, Signal):
                    signals.add(robj)
        elif isinstance(obj, Cat):
            for cobj in obj.l:
                assert isinstance(cobj, Signal)
                signals.add(cobj)

    add_obj(obj)
    for attr_name in dir(obj):
        if attr_name[:2] == "__" and attr_name[-2:] == "__":
            continue
        add_obj(getattr(obj, attr_name))
    if recurse:
        if isinstance(obj, Module):
            for submod_name, submod in obj._submodules:
                signals |= get_signals(submod, recurse=True)

    return signals

