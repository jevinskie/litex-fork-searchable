#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@>
# SPDX-License-Identifier: BSD-2-Clause

import logging
import os
import sys
import subprocess
from shutil import which

from migen.fhdl.structure import _Fragment
from litex import get_data_mod
from litex.build import tools
from litex.build.generic_platform import *
from litex.build.sim.common import SimClocker
from litex.build.sim.verilator import _generate_sim_h
from litex.build.sim.vpi import generate_vpi_init_generated_cpp

sim_directory = os.path.abspath(os.path.dirname(__file__))
core_directory = os.path.join(sim_directory, 'core')

_logger = logging.getLogger("Questa")



def _generate_sim_config(config):
    content = config.get_json(require_clockers=False)
    tools.write_to_file("sim_config.js", content)

def _generate_sim_variables(build_name, sources, include_paths,
                            opt_level, extra_mods, extra_mods_path, questa_flags=""):
    tapcfg_dir = get_data_mod("misc", "tapcfg").data_location
    include = ""
    for path in include_paths:
        include += "-I"+path+" "
    content = f"""\
TOPLEVEL := {build_name}
OPT_LEVEL ?= {opt_level}
QUESTA_FLAGS ?= {questa_flags}
VERILOG_SRCS := {" ".join([s[0] for s in sources])}
SRC_DIR := {core_directory}
INC_DIR := {include}
TAPCFG_DIRECTORY := {tapcfg_dir}
"""

    if extra_mods:
        modlist = " ".join(extra_mods)
        content += "EXTRA_MOD_LIST = " + modlist + "\n"
        content += "EXTRA_MOD_BASE_DIR = " + extra_mods_path + "\n"
        tools.write_to_file(extra_mods_path + "/variables.mak", content)

    tools.write_to_file("variables.mak", content)

def _build_sim(build_name):
    makefile = os.path.join(core_directory, 'Makefile.questa')
    build_script_contents = f"""\
#!/usr/bin/env bash
set -e -u -x -o pipefail
rm -rf obj_dir/
make -C . -f {makefile} "$@"
"""
    build_script_file = "build_" + build_name + ".sh"
    tools.write_to_file(build_script_file, build_script_contents, force_unix=True, chmod=0o755)

def _compile_sim(build_name, verbose):
    _logger.info("Sim gateware building...")
    build_script_file = "build_" + build_name + ".sh"
    p = subprocess.Popen(["bash", build_script_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output, _ = p.communicate()
    output = output.decode('utf-8')
    if p.returncode != 0:
        error_messages = []
        lines = output.splitlines()
        for i, l in enumerate(lines):
            if verbose or "error" in l.lower() or i >= len(lines) - 25:
                error_messages.append(l)
        raise OSError("Subprocess failed with {}\n{}".format(p.returncode, "\n".join(error_messages)))
    if verbose:
        print(output)
    _logger.info("Sim gateware built.")

def _run_sim(build_name, as_root=False, interactive=True):
    run_script_contents = "#!/usr/bin/env bash\nset -e -u -x -o pipefail\n"
    if which("litex_privesc") is not None:
        run_script_contents += "litex_privesc " if as_root else ""
    else:
        run_script_contents += "sudo " if as_root else ""
    run_script_contents += f"vsim -c {build_name} -pli ./litex_vpi.so -no_autoacc -undefsyms=off -do \"run -a\"\n"
    run_script_file = "run_" + build_name + ".sh"
    tools.write_to_file(run_script_file, run_script_contents, force_unix=True, chmod=0o755)
    if sys.platform != "win32" and interactive:
        import termios
        termios_settings = termios.tcgetattr(sys.stdin.fileno())
    try:
        r = subprocess.call(["bash", run_script_file])
        if r != 0:
            raise OSError("Subprocess failed")
    except:
        pass
    if sys.platform != "win32" and interactive:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, termios_settings)


class SimQuestaToolchain:
    def _add_clockers(self, soc, sim_config):
        clks = {}
        for mod in sim_config.modules:
            if mod["module"] != "clocker":
                continue
            clks[mod["interface"][0].removesuffix("_clk")] = mod["args"]
            sim_config.modules.remove(mod)

        for cd, params in clks.items():
            soc.submodules += SimClocker(soc.platform, cd, soc.platform.lookup_request(f"{cd}_clk"), params["freq_hz"], params["phase_deg"])

    def prefinalize(self, builder, verbose=False, **kwargs):
        self._add_clockers(builder.soc, kwargs["sim_config"])

    def build(self, platform, fragment,
            build_dir        = "build",
            build_name       = "sim_questa",
            serial           = "console",
            build            = True,
            run              = True,
            verbose          = False,
            sim_config       = None,
            opt_level        = "O3",
            trace            = False,
            trace_fst        = False,
            trace_start      = 0,
            trace_end        = -1,
            regular_comb     = False,
            interactive      = True,
            pre_run_callback = None,
            extra_mods       = None,
            extra_mods_path  = ""):

        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        cwd = os.getcwd()
        os.chdir(build_dir)

        if build:
            self._add_clockers(fragment, sim_config)
            # Finalize design
            if not isinstance(fragment, _Fragment):
                fragment = fragment.get_fragment()
            platform.finalize(fragment)

            # Generate verilog
            v_output = platform.get_verilog(fragment,
                name         = build_name,
                regular_comb = regular_comb
            )
            named_sc, named_pc = platform.resolve_signals(v_output.ns)
            v_file = build_name + ".v"
            v_output.write(v_file)
            platform.add_source(v_file)

            # Generate cpp header/main/variables
            _generate_sim_h(platform)
            generate_vpi_init_generated_cpp(build_name, platform)

            defs_args = [f"+define+{d}{f'={v}' if v is not None else ''}" \
                            for d, v in platform.compiler_definitions.items()]
            inc_args = [f"+incdir+{d}" for d in platform.verilog_include_paths]
            vlog_args = ["-sv", *defs_args, *inc_args]
            questa_flags = " ".join(vlog_args)

            _generate_sim_variables(build_name,
                                    platform.sources,
                                    platform.verilog_include_paths,
                                    opt_level,
                                    extra_mods,
                                    extra_mods_path,
                                    questa_flags=questa_flags)

            # Generate sim config
            if sim_config:
                _generate_sim_config(sim_config)

            # Build
            _build_sim(build_name)

        # Run
        if run:
            if pre_run_callback is not None:
                pre_run_callback(v_output.ns)
            if which("vlog") is None:
                msg = "Unable to find Questa toolchain, please either:\n"
                msg += "- Install Questa.\n"
                msg += "- Add Questa toolchain to your $PATH."
                raise OSError(msg)
            _compile_sim(build_name, verbose)
            run_as_root = False
            if sim_config.has_module("ethernet") \
               or sim_config.has_module("xgmii_ethernet") \
               or sim_config.has_module("gmii_ethernet"):
                run_as_root = True
            _run_sim(build_name, as_root=run_as_root, interactive=interactive)

        os.chdir(cwd)

        if build:
            return v_output.ns

def questa_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Questa toolchain options")
    toolchain_group.add_argument("--trace",        action="store_true", help="Enable Tracing.")
    toolchain_group.add_argument("--trace-fst",    action="store_true", help="Enable FST tracing.")
    toolchain_group.add_argument("--trace-start",  default="0",         help="Time to start tracing (ps).")
    toolchain_group.add_argument("--trace-end",    default="-1",        help="Time to end tracing (ps).")
    toolchain_group.add_argument("--opt-level",    default="O3",        help="Compilation optimization level.")
    toolchain_group.add_argument("--non-interactive", dest="interactive", action="store_false",
        help="Run simulation without user input.")


def questa_build_argdict(args):
    return {
        "trace"       : args.trace,
        "trace_fst"   : args.trace_fst,
        "trace_start" : int(float(args.trace_start)),
        "trace_end"   : int(float(args.trace_end)),
        "opt_level"   : args.opt_level,
        "interactive" : args.interactive
    }
