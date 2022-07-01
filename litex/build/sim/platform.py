#
# This file is part of LiteX.
#
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2017 Pierre-Olivier Vauboin <po@lambdaconcept>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import argparse

from migen.fhdl.structure import Signal, If, Finish
from migen.fhdl.module import Module
from migen.genlib.record import Record

from litex.build.generic_platform import GenericPlatform, Pins
from litex.build.sim import common, iverilog, verilator
from litex.soc.interconnect.csr import AutoCSR, CSR, CSRStorage
from litex.build.sim.verilator import verilator_build_args, verilator_build_argdict
from litex.build.sim.iverilog import iverilog_build_args, iverilog_build_argdict


def sim_build_args(parser):
    tc_arg_name = "--sim-toolchain"
    tc_arg_kws = dict(default="verilator", help="Simulation toolchain")
    parser.add_argument(tc_arg_name, **tc_arg_kws)
    stub_parser = argparse.ArgumentParser(parser.description, add_help=False)
    stub_parser.add_argument(tc_arg_name, **tc_arg_kws)
    stub_args = stub_parser.parse_known_args()[0]
    try:
        {
            "verilator": verilator_build_args,
            "iverilog": iverilog_build_args,
        }[stub_args.sim_toolchain](parser)
    except KeyError:
        raise NotImplementedError(f"Simulation toolchain '{stub_args.sim_toolchain}' is not supported.")


def sim_build_argdict(args):
    try:
        return {
            "verilator": verilator_build_argdict,
            "iverilog": iverilog_build_argdict, 
        }[args.sim_toolchain](args)
    except KeyError:
        raise NotImplementedError(f"Simulation toolchain '{args.sim_toolchain}' is not supported.")


class SimPlatform(GenericPlatform):
    def __init__(self, device, io, name="sim", toolchain="verilator", **kwargs):
        if "sim_trace" not in (iface[0] for iface in io):
            io.append(("sim_trace", 0, Pins(1)))
        GenericPlatform.__init__(self, device, io, name=name, **kwargs)
        self.sim_requested = []
        if toolchain == "verilator":
            self.toolchain = verilator.SimVerilatorToolchain()
        elif toolchain == "iverilog":
            self.toolchain = iverilog.SimIcarusToolchain()
        elif toolchain == "questa":
            raise NotImplementedError("TODO: questa")
        elif toolchain == "cocotb":
            raise NotImplementedError("TODO: cocotb")
        else:
            raise NotImplementedError(f"Unknown toolchain {toolchain}")
        # we must always request the sim_trace signal
        self.trace = self.request("sim_trace")

    def request(self, name, number=None, loose=False):
        index = ""
        if number is not None:
            index = str(number)
        obj = GenericPlatform.request(self, name, number=number, loose=loose)
        siglist = []
        if isinstance(obj, Signal):
            siglist.append((name, obj.nbits, name))
        elif isinstance(obj, Record):
            for subsignal, dummy in obj.iter_flat():
                subfname = subsignal.backtrace[-1][0]
                prefix = "{}{}_".format(name, index)
                subname = subfname.split(prefix)[1]
                siglist.append((subname, subsignal.nbits, subfname))
        self.sim_requested.append((name, index, siglist))
        return obj

    def get_verilog(self, *args, special_overrides=dict(), **kwargs):
        so = dict(common.sim_special_overrides)
        so.update(special_overrides)
        return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

    def build(self, *args, **kwargs):
        return self.toolchain.build(self, *args, **kwargs)

    def add_debug(self, module, reset=0):
        module.submodules.sim_trace = SimTrace(self.trace, reset=reset)
        module.submodules.sim_marker = SimMarker()
        module.submodules.sim_finish = SimFinish()
        module.add_csr("sim_trace")
        module.add_csr("sim_marker")
        module.add_csr("sim_finish")
        self.trace = None

# Sim debug modules --------------------------------------------------------------------------------

class SimTrace(Module, AutoCSR):
    """Start/stop simulation tracing from software/gateware"""
    def __init__(self, pin, reset=0):
        # set from software/gateware
        self.enable = CSRStorage(reset=reset)
        # used by simulator to start/stop dump
        self.comb += pin.eq(self.enable.storage)

class SimMarker(Module, AutoCSR):
    """Set simulation markers from software/gateware

    This is useful when analysing trace dumps. Change the marker value from
    software/gateware, and then check the *_marker_storage signal in GTKWave.
    """
    def __init__(self, size=8):
        # set from software
        self.marker = CSRStorage(size)

class SimFinish(Module, AutoCSR):
    """Finish simulation from software"""
    def __init__(self):
        # set from software
        self.finish = CSR()
        self.sync += If(self.finish.re, Finish())
