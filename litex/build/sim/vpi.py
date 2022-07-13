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
vpi_handles.{topname} = vpi_handle_by_name("{build_name}.{topname}", nullptr);
assert(vpi_handles.{topname});
s_cb_data {topname}_cbd{{
    .reason    = cbValueChange,
    .cb_rtn    = signal_{uint_ty}_change_cb,
    .obj       = vpi_handles.{topname},
    .time      = &t,
    .value     = &v,
    .user_data = (char *)&sig_vals.{topname}
}};
const auto {topname}_cb = vpi_register_cb(&{topname}_cbd);
assert({topname}_cb && vpi_free_object({topname}_cb));
{name}{idx}[{sigidx}].signal = &sig_vals.{topname};

"""
    return "\n".join([indent + l for l in txt.splitlines()]) + "\n"

def _register_writeback(build_name, name, idx, sigidx, topname, uint_ty, indent=""):
    txt = f"""\
if (sig_vals.{topname} != last_sig_vals.{topname}) {{
    v.value.integer = sig_vals.{topname};
    assert(!vpi_put_value(vpi_handles.{topname}, &v, nullptr, vpiNoDelay));
}}

"""

#     if topname != "sys_clk":
#         txt += f"""\
# if (sig_vals.{topname} != last_sig_vals.{topname}) {{
#     fprintf(stderr, \"{topname} old: 0x%08x new: 0x%08x\\n\", last_sig_vals.{topname}, sig_vals.{topname});
# }}
# """

    return "\n".join([indent + l for l in txt.splitlines()]) + "\n"

def _gen_register_cb_func(build_name, platform):
    txt = """\
extern "C" void litex_vpi_signals_register_callbacks() {
    static s_vpi_time t{.type = vpiSuppressTime};
    static s_vpi_value v{.format = vpiIntVal};

"""
    for name, idx, siglist in platform.sim_requested:
        idx_int = 0 if not idx else int(idx)
        for sigidx, siginfo in enumerate(siglist):
            signame, sigbits, topname = siginfo
            txt += _register_cb(build_name, name, idx, sigidx, topname, _uint_ty(sigbits), indent=" " * 4)
        txt += f"""\
    assert(!litex_sim_register_pads({name}{idx}, "{name}", {idx_int}));

"""
    txt += """\
}

extern "C" void litex_vpi_signals_writeback() {
    static vpi_values_t last_sig_vals{};
    if (!memcmp(&sig_vals, &last_sig_vals, sizeof(sig_vals))) {
        return;
    }

    s_vpi_value v{.format = vpiIntVal};

"""
    for name, idx, siglist in platform.sim_requested:
        idx_int = 0 if not idx else int(idx)
        for sigidx, siginfo in enumerate(siglist):
            signame, sigbits, topname = siginfo
            txt += _register_writeback(build_name, name, idx, sigidx, topname, _uint_ty(sigbits), indent=" " * 4)
    txt += """\
    memcpy(&last_sig_vals, &sig_vals, sizeof(last_sig_vals));
}
"""
    return txt

def generate_vpi_init_generated_cpp(build_name, platform):
    _check_signal_bitwidth_compat(platform)

    txt = "struct vpi_values_t {\n"
    num_sigs = 0
    for name, idx, siglist in platform.sim_requested:
        for signame, sigbits, topname in siglist:
            txt += f"    PLI_INT32 {topname};\n"
            num_sigs += 1
    txt += f"""\
}};

static_assert(sizeof(vpi_values_t) == {num_sigs} * sizeof(int32_t), "Struct padding detected");
static vpi_values_t sig_vals;

"""

    txt += "struct vpi_handles_t {\n";
    for name, idx, siglist in platform.sim_requested:
        for signame, sigbits, topname in siglist:
            txt += f"    vpiHandle {topname};\n"
    txt +="""\
};

static vpi_handles_t vpi_handles;
"""



    txt += _gen_register_cb_func(build_name, platform)
    txt += "\n\n"

    tools.write_to_file("vpi_init_generated.cpp", txt)

