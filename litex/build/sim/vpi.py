#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build import tools

def vpi_uint_ty(sigbits):
    if 1 <= sigbits <= 8:
        return "uint8_t"
    elif 9 <= sigbits <= 16:
        return "uint16_t"
    elif 17 <= sigbits <= 32:
        return "uint32_t"
    raise ValueError(f"Can't get uint type for {sigbits} bits.")

def _check_signal_bitwidth_compat(platform):
    for name, idx, siglist in platform.sim_requested:
        for signame, sigbits, topname in siglist:
            if sigbits > 32:
                raise NotImplementedError(
                    "VPI only supports up to 32 bit values but " +
                    f"module '{name}' signal '{signame}' is {sigbits} bits."
                )

def _register_cb(build_name, topname, indent=""):
    txt = ""
    return txt

def generate_vpi_init_generated_cpp(build_name, platform):
    _check_signal_bitwidth_compat(platform)

    txt = ""

    for name, idx, siglist in platform.sim_requested:
        for signame, sigbits, topname in siglist:
            txt += f"ALIGNED(4) static {vpi_uint_ty(sigbits)} sig_{topname}_val;\n"

    tools.write_to_file("vpi_init_generated.cpp", txt)

