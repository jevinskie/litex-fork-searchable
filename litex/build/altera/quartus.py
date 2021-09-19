#
# This file is part of LiteX.
#
# Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 msloniewski <marcin.sloniewski@gmail.com>
# Copyright (c) 2019 vytautasb <v.buitvydas@limemicro.com>
# SPDX-License-Identifier: BSD-2-Clause

from pathlib import Path
import os
import subprocess
import sys
import math
from shutil import which

from migen.fhdl.structure import _Fragment, _Assign, _Slice

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools

# IO/Placement Constraints (.qsf) ------------------------------------------------------------------

def _format_constraint(c, signame, fmt_r):
    # IO location constraints
    if isinstance(c, Pins):
        tpl = "set_location_assignment -comment \"{name}\" -to {signame} Pin_{pin}"
        return tpl.format(signame=signame, name=fmt_r, pin=c.identifiers[0])

    # IO standard constraints
    elif isinstance(c, IOStandard):
        tpl = "set_instance_assignment -name io_standard -comment \"{name}\" \"{std}\" -to {signame}"
        return tpl.format(signame=signame, name=fmt_r, std=c.name)

    # Others constraints
    elif isinstance(c, Misc):
        if not isinstance(c.misc, str) and len(c.misc) == 2:
            tpl = "set_instance_assignment -comment \"{name}\" -name {misc[0]} \"{misc[1]}\" -to {signame}"
            return tpl.format(signame=signame, name=fmt_r, misc=c.misc)
        else:
            tpl = "set_instance_assignment -comment \"{name}\"  -name {misc} -to {signame}"
            return tpl.format(signame=signame, name=fmt_r, misc=c.misc)

def _format_qsf_constraint(signame, pin, others, resname):
    fmt_r = "{}:{}".format(*resname[:2])
    if resname[2] is not None:
        fmt_r += "." + resname[2]
    fmt_c = [_format_constraint(c, signame, fmt_r) for c in ([Pins(pin)] + others)]
    return '\n'.join(fmt_c)

def _is_virtual_pin(pin_name):
    virtual_pins = (
        'altera_reserved_tms',
        'altera_reserved_tck',
        'altera_reserved_tdi',
        'altera_reserved_tdo',
    )
    return pin_name in virtual_pins

def _build_qsf_constraints(named_sc, named_pc):
    qsf = []
    for sig, pins, others, resname in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                if _is_virtual_pin(p):
                    continue
                qsf.append(_format_qsf_constraint("{}[{}]".format(sig, i), p, others, resname))
        else:
            if _is_virtual_pin(pins[0]):
                continue
            qsf.append(_format_qsf_constraint(sig, pins[0], others, resname))
    if named_pc:
        qsf.append("\n\n".join(named_pc))
    return "\n".join(qsf)

# Timing Constraints (.sdc) ------------------------------------------------------------------------

def _build_sdc(clocks, clock_pads, false_paths, vns, named_sc, build_name, additional_sdc_commands, fragment):
    sdc = []
    real_clock_pads = []
    for sig, frag in clock_pads.items():
        if isinstance(frag[0], _Slice):
            real_sig = frag[0].value
            real_clock_pads.append(real_sig)

    # Clock constraints
    for clk, period in sorted(clocks.items(), key=lambda x: x[0].duid):
        clk_rhs = None
        clk_buf_in = None
        clk_buf_out = None
        clk_port = None
        clk_driver = None

        for sp in fragment.specials:
            if not hasattr(sp, 'attr') or 'clkbuf_clkctrl' not in sp.attr:
                continue
            if clk is not sp.items[1].expr:
                continue
            clk_buf_in = sp.items[0].expr
            clk_driver = clk_buf_in
            clk_buf_out = sp.items[1].expr
            print('found clkbuf')

        if clk_buf_in is None:
            for cs in fragment.comb:
                if not isinstance(cs, _Assign):
                    continue
                if cs.l is clk:
                    clk_driver = cs.r
                    break
        else:
            for cs in fragment.comb:
                if not isinstance(cs, _Assign):
                    continue
                if cs.l is clk_buf_in:
                    clk_driver = cs.r
                    break

        if clk_driver is not None:
            print(f'found clk_driver: {clk_driver} for clk: {clk}')

        is_port = False
        has_port = clk_driver is not None and clk_driver in real_clock_pads
        for sig, pins, others, resname in named_sc:
            clk_sig_name = vns.get_name(clk)
            if sig == clk_sig_name:
                is_port = True
        if is_port:
            tpl = "create_clock -name {clk} -period {period} [get_ports {{{clk}}}]"
            sdc.append(tpl.format(clk=vns.get_name(clk), period=str(period)))
        else:
            collection = "[get_nets {{{clk}}}]"
            if has_port:
                collection = "[add_to_collection  [get_nets {{{clk}}}] [get_nodes {{{clk_rhs}}}]]"
            tpl = "create_clock -name {clk} -period {period} " + collection
            sdc.append(tpl.format(clk=vns.get_name(clk), clk_rhs=vns.get_name(clk_driver) if clk_driver is not None else None, period=str(period)))

    # False path constraints
    for from_, to in sorted(false_paths, key=lambda x: (x[0].duid, x[1].duid)):
        tpl = "set_false_path -from [get_clocks {{{from_}}}] -to [get_clocks {{{to}}}]"
        sdc.append(tpl.format(from_=vns.get_name(from_), to=vns.get_name(to)))

    # Add additional commands
    sdc += additional_sdc_commands

    # Generate .sdc
    tools.write_to_file("{}.sdc".format(build_name), "\n".join(sdc))

# Project (.qsf) -----------------------------------------------------------------------------------

def _build_qsf(device, ips, sources, vincpaths, named_sc, named_pc, build_name, additional_qsf_commands):
    qsf = []

    # Set device
    qsf.append("set_global_assignment -name DEVICE {}".format(device))

    # Add sources
    for filename, language, library in sources:
        if language == "verilog": language = "systemverilog" # Enforce use of SystemVerilog
        tpl = "set_global_assignment -name {lang}_FILE {path} -library {lib}"
        # Do not add None type files
        if language is not None:
            qsf.append(tpl.format(lang=language.upper(), path=filename.replace("\\", "/"), lib=library))
        # Check if the file is a header. Those should not be explicitly added to qsf,
        # but rather included in include search_path
        else:
            if filename.endswith(".svh") or filename.endswith(".vh"):
                fpath = os.path.dirname(filename)
                if fpath not in vincpaths:
                    vincpaths.append(fpath)

    # Add ips
    for filename in ips:
        tpl = "set_global_assignment -name QSYS_FILE {filename}"
        qsf.append(tpl.replace(filename=filename.replace("\\", "/")))

    # Add include paths
    for path in vincpaths:
        qsf.append("set_global_assignment -name SEARCH_PATH {}".format(path.replace("\\", "/")))

    # Set top level
    qsf.append("set_global_assignment -name top_level_entity " + build_name)

    # Add io, placement constraints
    qsf.append(_build_qsf_constraints(named_sc, named_pc))

    # Set timing constraints
    qsf.append("set_global_assignment -name SDC_FILE {}.sdc".format(build_name))
    qsf.append("set_global_assignment -name SDC_FILE jtag.sdc")
    jtag_sdc_txt = open(Path(__file__).parent / 'jtag.sdc').read()
    tools.write_to_file("jtag.sdc", jtag_sdc_txt)

    # Add additional commands
    qsf += additional_qsf_commands

    # Generate .qsf
    tools.write_to_file("{}.qsf".format(build_name), "\n".join(qsf))

# General Config (quartus.ini) ---------------------------------------------------------------------

def _build_quartus_ini():
    ini = []

    ini.append("vqmo_third_party_encrypted_core_support = 1")

    # Generate quartus.ini
    tools.write_to_file("quartus.ini", "\n".join(ini) + "\n")

# Script -------------------------------------------------------------------------------------------

def _build_script(build_name, create_rbf, create_svf):
    if sys.platform in ["win32", "cygwin"]:
        script_contents = "REM Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        script_file = "build_" + build_name + ".bat"
    else:
        script_contents = "# Autogenerated by LiteX / git: " + tools.get_litex_git_revision()
        script_file = "build_" + build_name + ".sh"
    timing_tcl_file = "timing-reports.tcl"
    script_contents += """
set -e -u -x -o pipefail
quartus_map --read_settings_files=on  --write_settings_files=off {build_name} -c {build_name}
quartus_cdb --read_settings_files=off --write_settings_files=off {build_name} -c {build_name} --vqm=atom-netlist-map.vqm
quartus_fit --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_asm --read_settings_files=off --write_settings_files=off {build_name} -c {build_name}
quartus_cdb --read_settings_files=off --write_settings_files=off {build_name} -c {build_name} --vqm=atom-netlist-fit.vqm
quartus_sta {build_name} -c {build_name}
quartus_sta -t {timing_tcl_file} -project {build_name}
"""
    if create_rbf:
        script_contents += """
if [ -f "{build_name}.sof" ]
then
    quartus_cpf -c {build_name}.sof {build_name}.rbf
fi
"""
    if create_svf:
        script_contents += """
if [ -f "{build_name}.sof" ]
then
    quartus_cpf -c --frequency 10MHz --voltage 3.3 --operation p {build_name}.sof {build_name}-program.svf
    quartus_cpf -c --frequency 10MHz --voltage 3.3 --operation v {build_name}.sof {build_name}-verify.svf
fi
"""
    script_contents = script_contents.format(build_name=build_name, timing_tcl_file=timing_tcl_file)
    tools.write_to_file(script_file, script_contents, force_unix=True)

    timing_tcl_contents = """
package require cmdline
set options {\
    { "project.arg" "" "Project name" }
}
array set opts [::cmdline::getoptions quartus(args) $options]

project_open $opts(project) -current_revision
create_timing_netlist
read_sdc
update_timing_netlist

report_sdc -ignored -file "sdc_constraints.rpt"

foreach_in_collection op [get_available_operating_conditions] {
  set_operating_conditions $op

  report_timing -setup -npaths 25 -detail full_path -multi_corner \
    -panel_name "Critical paths"

  report_timing -setup -npaths 25 -detail full_path -multi_corner \
    -file "timing_paths_full_$op.rpt" \
    -panel_name "Critical paths"

  report_timing -setup -npaths 25 -detail full_path -multi_corner \
    -file "timing_paths_html_$op.html" \
    -panel_name "Critical paths for $op"
}

delete_timing_netlist
project_close
"""
    tools.write_to_file(timing_tcl_file, timing_tcl_contents, force_unix=True)

    return script_file

def _run_script(script):
    if sys.platform in ["win32", "cygwin"]:
        shell = ["cmd", "/c"]
    else:
        shell = ["bash"]

    if which("quartus_map") is None:
        msg = "Unable to find Quartus toolchain, please:\n"
        msg += "- Add Quartus toolchain to your $PATH."
        raise OSError(msg)

    if subprocess.call(shell + [script]) != 0:
        raise OSError("Error occured during Quartus's script execution.")

# AlteraQuartusToolchain ---------------------------------------------------------------------------

class AlteraQuartusToolchain:
    attr_translate = {
        "keep":            ("keep",       "true"),
        # "no_retiming":     ("keep",       "true"),
        "async_reg":       ("async_reg",  "true"),
        "mr_ff":           ("mr_ff",      "true"), # user-defined attribute
        "ars_ff1":         ("ars_ff1",    "true"), # user-defined attribute
        "ars_ff2":         ("ars_ff2",    "true"), # user-defined attribute
        "arsss_ff":        ("arsss_ff",   "true"), # user-defined attribute
        "clkbuf_clkctrl":  ("clkbuf_clkctrl", "true"), # user-defined attribute
        "rd_ff":           ("rd_ff",      "true"), # user-defined attribute
    }

    def __init__(self):
        self.clocks      = dict()
        self.clock_pads  = dict()
        self.false_paths = set()
        self.additional_sdc_commands = []
        self.additional_qsf_commands = []

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        **kwargs):

        # Create build directory
        cwd = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)

        # Generate design timing constraints file (.sdc)
        _build_sdc(
            clocks                  = self.clocks,
            clock_pads              = self.clock_pads,
            false_paths             = self.false_paths,
            vns                     = v_output.ns,
            named_sc                = named_sc,
            build_name              = build_name,
            additional_sdc_commands = self.additional_sdc_commands,
            fragment                = fragment)

        # Generate design project and location constraints file (.qsf)
        _build_qsf(
            device                  = platform.device,
            ips                     = platform.ips,
            sources                 = platform.sources,
            vincpaths               = platform.verilog_include_paths,
            named_sc                = named_sc,
            named_pc                = named_pc,
            build_name              = build_name,
            additional_qsf_commands = self.additional_qsf_commands)

        _build_quartus_ini()

        # Generate build script
        script = _build_script(build_name, platform.create_rbf, platform.create_svf)

        # Run
        if run:
            _run_script(script)

        os.chdir(cwd)

        return v_output.ns

    def add_period_constraint(self, platform, clk, period):
        clk.attr.add("keep")
        period = math.floor(period*1e3)/1e3 # round to lowest picosecond
        if clk in self.clocks:
            if period != self.clocks[clk]:
                raise ValueError("Clock already constrained to {:.2f}ns, new constraint to {:.2f}ns"
                    .format(self.clocks[clk], period))
        self.clocks[clk] = period

    def associate_clock_and_pad(self, platform, clk, clk_pad):
        if clk in self.clock_pads:
            if clk_pad not in self.clock_pads:
                self.clock_pads[clk].append(clk_pad)
        else:
            self.clock_pads[clk] = list(clk_pad)

    def add_false_path_constraint(self, platform, from_, to):
        from_.attr.add("keep")
        to.attr.add("keep")
        if (to, from_) not in self.false_paths:
            self.false_paths.add((from_, to))
