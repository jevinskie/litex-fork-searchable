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

sim_directory = os.path.abspath(os.path.dirname(__file__))
core_directory = os.path.join(sim_directory, 'core')

_logger = logging.getLogger("Icarus")



def _generate_sim_config(config):
    content = config.get_json()
    tools.write_to_file("sim_config.js", content)


def _build_sim(build_name, sources, trace_fst=False):
    makefile = os.path.join(core_directory, 'Makefile.iverilog')
    cc_srcs = []
    for filename, language, library, *copy in sources:
        cc_srcs.append("--cc " + filename + " ")
    build_script_contents = """\
#!/usr/bin/env bash
set -e -u -x -o pipefail
rm -rf obj_dir/
make -C . -f {} {} {}
iverilog -o {} {}
""".format(
    # make
    makefile,
    f"CC_SRCS=\"{''.join(cc_srcs)}\"",
    "TRACE_FST=1" if trace_fst else "",
    # iverilog
    build_name,
    " ".join([s[0] for s in sources])
    )
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
        for l in output.splitlines():
            if verbose or "error" in l.lower():
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
    run_script_contents += f"./{build_name}\n"
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


class SimIcarusToolchain:
    def _add_clockers(self, soc, sim_config):
        print(f"vars(soc): {vars(soc)}")
        for mod in sim_config.modules:
            if mod["module"] != "clocker":
                continue


    def build(self, platform, fragment,
            build_dir        = "build",
            build_name       = "sim_iverilog",
            serial           = "console",
            build            = True,
            run              = True,
            verbose          = False,
            sim_config       = None,
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

        if not build_name.endswith("_iverilog"):
            build_name += "_iverilog"

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

            # Generate sim config
            if sim_config:
                _generate_sim_config(sim_config)

            # Build
            _build_sim(build_name, platform.sources, trace_fst)

        # Run
        if run:
            if pre_run_callback is not None:
                pre_run_callback(v_output.ns)
            if which("iverilog") is None:
                msg = "Unable to find Icarus Verilog toolchain, please either:\n"
                msg += "- Install Icarus Verilog.\n"
                msg += "- Add Icarus Verilog toolchain to your $PATH."
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

def iverilog_build_args(parser):
    toolchain_group = parser.add_argument_group(title="Icarus Verilog toolchain options")
    toolchain_group.add_argument("--trace",        action="store_true", help="Enable Tracing.")
    toolchain_group.add_argument("--trace-fst",    action="store_true", help="Enable FST tracing.")
    toolchain_group.add_argument("--trace-start",  default="0",         help="Time to start tracing (ps).")
    toolchain_group.add_argument("--trace-end",    default="-1",        help="Time to end tracing (ps).")
    toolchain_group.add_argument("--non-interactive", dest="interactive", action="store_false",
        help="Run simulation without user input.")


def iverilog_build_argdict(args):
    return {
        "trace"       : args.trace,
        "trace_fst"   : args.trace_fst,
        "trace_start" : int(float(args.trace_start)),
        "trace_end"   : int(float(args.trace_end)),
        "interactive" : args.interactive
    }
