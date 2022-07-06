#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build import tools

def _uint_ty(sigbits):
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

def _register_cb(build_name, name, idx, sigidx, topname, uint_ty, indent=""):
    txt = f"""\
const auto {topname}_hdl = vpi_handle_by_name("{build_name}.{topname}", nullptr);
assert({topname}_hdl);
s_cb_data {topname}_cbd{{
    .reason    = cbValueChange,
    .cb_rtn    = signal_{uint_ty}_change_cb,
    .obj       = {topname}_hdl,
    .time      = &time_rec,
    .value     = &val_rec,
    .user_data = (char *)&sig_vals.{topname}
}};
const auto {topname}_cb = vpi_register_cb(&{topname}_cbd);
assert({topname}_cb && vpi_free_object({topname}_cb) && vpi_free_object({topname}_hdl));
{name}{idx}[{sigidx}].signal = &sig_vals.{topname};

"""
    return "\n".join([indent + l for l in txt.splitlines()]) + "\n"

def _gen_register_cb_func(build_name, platform):
    txt = """\
extern "C" void litex_vpi_register_signal_callbacks() {
    static s_vpi_time time_rec{.type = vpiSuppressTime};
    static s_vpi_value val_rec{.format = vpiIntVal};

"""
    for name, idx, siglist in platform.sim_requested:
        idx_int = 0 if not idx else int(idx)
        for sigidx, siginfo in enumerate(siglist):
            signame, sigbits, topname = siginfo
            txt += _register_cb(build_name, name, idx, sigidx, topname, _uint_ty(sigbits), indent=" " * 4)
        txt += f"""\
    assert(!litex_sim_register_pads({name}{idx}, "{name}", {idx_int}));

"""
    txt += "}\n"
    return txt

def generate_vpi_init_generated_cpp(build_name, platform):
    _check_signal_bitwidth_compat(platform)

    txt = "struct vpi_values {\n"

    num_sigs = 0
    for name, idx, siglist in platform.sim_requested:
        for signame, sigbits, topname in siglist:
            txt += f"    PLI_INT32 {topname};\n"
            num_sigs += 1
    txt += f"""\
}};

static_assert(sizeof(vpi_values) == {num_sigs} * sizeof(int32_t), "Struct padding detected");
static vpi_values sig_vals;

"""

    txt += _gen_register_cb_func(build_name, platform)
    txt += "\n\n"

    tools.write_to_file("vpi_init_generated.cpp", txt)

