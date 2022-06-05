#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen.genlib.record import Record
from migen.fhdl.module import Module
from migen.fhdl.structure import Signal, Constant
import migen.fhdl.specials
from migen.fhdl.specials import Instance

from litex.gen.fhdl.verilog import _print_expression

def get_signals(obj, recurse=False):
    signals = set()
    for attr_name in dir(obj):
        if attr_name[:2] == "__" and attr_name[-2:] == "__":
            continue
        attr = getattr(obj, attr_name)
        if isinstance(attr, Signal):
            signals.add(attr)
        elif isinstance(attr, Record):
            for robj in attr.flatten():
                if isinstance(robj, Signal):
                    signals.add(robj)
        elif recurse and isinstance(attr, Module):
            signals |= get_signals(attr, recurse=True)

    return signals

def rename_fsm(fsm, name):
    fsm.state.backtrace.append((f"{name}_next", None))
    fsm.next_state.backtrace.append((f"{name}_next_state", None))


# Helper to set Instance parameters to plain printing ----------------------------------------------

def instance_enable_plain_printing(instance):
    for item in instance.items:
        if isinstance(item, Instance.Parameter) and isinstance(item.value, Constant):
            item.value.print_plain = True


class InstancePlainParameters(Instance):
    def emit_verilog(instance, ns, add_data_file):
        instance_enable_plain_printing(instance)
        orig_print_expr = migen.fhdl.specials.verilog_printexpr
        migen.fhdl.specials.verilog_printexpr = _print_expression
        verilog = super().emit_verilog(instance, ns, add_data_file)
        migen.fhdl.specials.verilog_printexpr = orig_print_expr
        return verilog

