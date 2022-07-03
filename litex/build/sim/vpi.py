#
# This file is part of LiteX.
#
# Copyright (c) 2022 Jevin Sweval <jevinsweval@>
# SPDX-License-Identifier: BSD-2-Clause

from litex.build import tools


def generate_vpi_init_cpp(build_name, platform):
    txt = """\
#undef NDEBUG
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <vpi_user.h>

//extern "C" void litex_sim_dump()
//{
//}

extern "C" void litex_sim_init(void **out)
{
}

"""
    tools.write_to_file("vpi_init.cpp", txt)

