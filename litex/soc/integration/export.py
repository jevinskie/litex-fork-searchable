#
# This file is part of LiteX.
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2014-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 Dolu1990 <charles.papon.90@gmail.com>
# This file is Copyright (c) 2019 Gabriel L. Somlo <gsomlo@gmail.com>
# This file is Copyright (c) 2018 Jean-François Nguyen <jf@lambdaconcept.fr>
# This file is Copyright (c) 2019 Antmicro <www.antmicro.com>
# This file is Copyright (c) 2013 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2018 Sean Cross <sean@xobs.io>
# This file is Copyright (c) 2018 Sergiusz Bazanski <q3k@q3k.org>
# This file is Copyright (c) 2018-2016 Tim 'mithro' Ansell <me@mith.ro>
# This file is Copyright (c) 2015 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2018 William D. Jones <thor0505@comcast.net>
# This file is Copyright (c) 2020 Piotr Esden-Tempski <piotr@esden.net>
# SPDX-License-Identifier: BSD-2-Clause

import os
import json
import inspect
from shutil import which
from sysconfig import get_platform

from migen import *

from litex.soc.interconnect.csr import CSRStatus

from litex.build.tools import generated_banner

from litex.soc.doc.rst import reflow
from litex.soc.doc.module import gather_submodules, ModuleNotDocumented, DocumentedModule, DocumentedInterrupts
from litex.soc.doc.csr import DocumentedCSRRegion
from litex.soc.interconnect.csr import _CompoundCSR

# for generating a timestamp in the description field, if none is otherwise given
import datetime
import time

# CPU files ----------------------------------------------------------------------------------------

def get_cpu_mak(cpu, compile_software):
    # select between clang and gcc
    clang = os.getenv("CLANG", "")
    if clang != "":
        clang = bool(int(clang))
    else:
        clang = None
    if cpu.clang_triple is None:
        if clang:
            raise ValueError(cpu.name + " is not supported with clang.")
        else:
            clang = False
    else:
        # Default to gcc unless told otherwise
        if clang is None:
            clang = False
    assert isinstance(clang, bool)
    if clang:
        triple = cpu.clang_triple
        flags = cpu.clang_flags
    else:
        triple = cpu.gcc_triple
        flags = cpu.gcc_flags

    # select triple when more than one
    def select_triple(triple):
        r = None
        if not isinstance(triple, tuple):
            triple = (triple,)
        override = os.getenv("LITEX_ENV_CC_TRIPLE")
        if override:
            triple = (override,) + triple
        p = get_platform()
        for i in range(len(triple)):
            t = triple[i]
            # use native toolchain if host and target platforms are the same
            if t == 'riscv64-unknown-elf' and p == 'linux-riscv64':
                r = '--native--'
                break
            if which(t+"-gcc"):
                r = t
                break
        if r is None:
            if not compile_software:
                return "--not-found--"
            msg = "Unable to find any of the cross compilation toolchains:\n"
            for i in range(len(triple)):
                msg += "- " + triple[i] + "\n"
            raise OSError(msg)
        return r

    # return informations
    return [
        ("TRIPLE", select_triple(triple)),
        ("CPU", cpu.name),
        ("CPUFLAGS", flags),
        ("CPUENDIANNESS", cpu.endianness),
        ("CLANG", str(int(clang))),
        ("CPU_DIRECTORY", os.path.dirname(inspect.getfile(cpu.__class__))),
    ]


def get_linker_output_format(cpu):
    return "OUTPUT_FORMAT(\"" + cpu.linker_output_format + "\")\n"


def get_linker_regions(regions):
    r = "MEMORY {\n"
    for name, region in regions.items():
        r += "\t{} : ORIGIN = 0x{:08x}, LENGTH = 0x{:08x}\n".format(name, region.origin, region.length)
    r += "}\n"
    return r


# C Export -----------------------------------------------------------------------------------------

def get_git_header():
    from litex.build.tools import get_migen_git_revision, get_litex_git_revision
    r = generated_banner("//")
    r += "#ifndef __GENERATED_GIT_H\n#define __GENERATED_GIT_H\n\n"
    r += "#define MIGEN_GIT_SHA1 \"{}\"\n".format(get_migen_git_revision())
    r += "#define LITEX_GIT_SHA1 \"{}\"\n".format(get_litex_git_revision())
    r += "#endif\n"
    return r

def get_mem_header(regions):
    r = generated_banner("//")
    r += "#ifndef __GENERATED_MEM_H\n#define __GENERATED_MEM_H\n\n"
    for name, region in regions.items():
        r += "#ifndef {name}_BASE\n".format(name=name.upper())
        r += "#define {name}_BASE 0x{base:08x}L\n#define {name}_SIZE 0x{size:08x}\n".format(
            name=name.upper(), base=region.origin, size=region.length)
        r += "#endif\n\n"

    r += "#ifndef MEM_REGIONS\n"
    r += "#define MEM_REGIONS \"";
    for name, region in regions.items():
        r += f"{name.upper()} {' '*(8-len(name))} 0x{region.origin:08x} 0x{region.size:x} \\n"
    r = r[:-2]
    r += "\"\n"
    r += "#endif\n"

    r += "#endif\n"
    return r

def get_soc_header(constants, with_access_functions=True):
    r = generated_banner("//")
    r += "#ifndef __GENERATED_SOC_H\n#define __GENERATED_SOC_H\n"
    funcs = ""

    for name, value in constants.items():
        if value is None:
            r += "#define "+name+"\n"
            continue
        if isinstance(value, str):
            value = "\"" + value + "\""
            ctype = "const char *"
        else:
            value = str(value)
            ctype = "int"
        r += "#define "+name+" "+value+"\n"
        if with_access_functions:
            funcs += "static inline "+ctype+" "+name.lower()+"_read(void) {\n"
            funcs += "\treturn "+value+";\n}\n"

    if with_access_functions:
        r += "\n#ifndef __ASSEMBLER__\n"
        r += funcs
        r += "#endif // !__ASSEMBLER__\n"

    r += "\n#endif\n"
    return r

def _get_rw_functions_c(reg_name, reg_base, nwords, busword, alignment, read_only, with_access_functions):
    r = ""

    addr_str = "CSR_{}_ADDR".format(reg_name.upper())
    size_str = "CSR_{}_SIZE".format(reg_name.upper())
    r += "#define {} (CSR_BASE + {}L)\n".format(addr_str, hex(reg_base))
    r += "#define {} {}\n".format(size_str, nwords)

    size = nwords*busword//8
    if size > 8:
        # downstream should select appropriate `csr_[rd|wr]_buf_uintX()` pair!
        return r
    elif size > 4:
        ctype = "uint64_t"
    elif size > 2:
        ctype = "uint32_t"
    elif size > 1:
        ctype = "uint16_t"
    else:
        ctype = "uint8_t"

    stride = alignment//8;
    if with_access_functions:
        r += "static inline {} {}_read(void) {{\n".format(ctype, reg_name)
        if nwords > 1:
            r += "\t{} r = csr_read_simple(CSR_BASE + {}L);\n".format(ctype, hex(reg_base))
            for sub in range(1, nwords):
                r += "\tr <<= {};\n".format(busword)
                r += "\tr |= csr_read_simple(CSR_BASE + {}L);\n".format(hex(reg_base+sub*stride))
            r += "\treturn r;\n}\n"
        else:
            r += "\treturn csr_read_simple(CSR_BASE + {}L);\n}}\n".format(hex(reg_base))

        if not read_only:
            r += "static inline void {}_write({} v) {{\n".format(reg_name, ctype)
            for sub in range(nwords):
                shift = (nwords-sub-1)*busword
                if shift:
                    v_shift = "v >> {}".format(shift)
                else:
                    v_shift = "v"
                r += "\tcsr_write_simple({}, CSR_BASE + {}L);\n".format(v_shift, hex(reg_base+sub*stride))
            r += "}\n"
    return r


def get_csr_header(regions, constants, csr_base=None, with_access_functions=True):
    alignment = constants.get("CONFIG_CSR_ALIGNMENT", 32)
    r = generated_banner("//")
    if with_access_functions: # FIXME
        r += "#include <generated/soc.h>\n"
    r += "#ifndef __GENERATED_CSR_H\n#define __GENERATED_CSR_H\n"
    if with_access_functions:
        r += "#include <stdint.h>\n"
        r += "#include <system.h>\n"
        r += "#ifndef CSR_ACCESSORS_DEFINED\n"
        r += "#include <hw/common.h>\n"
        r += "#endif /* ! CSR_ACCESSORS_DEFINED */\n"
    csr_base = csr_base if csr_base is not None else regions[next(iter(regions))].origin
    r += "#ifndef CSR_BASE\n"
    r += "#define CSR_BASE {}L\n".format(hex(csr_base))
    r += "#endif\n"
    for name, region in regions.items():
        origin = region.origin - csr_base
        r += "\n/* "+name+" */\n"
        r += "#define CSR_"+name.upper()+"_BASE (CSR_BASE + "+hex(origin)+"L)\n"
        if not isinstance(region.obj, Memory):
            for csr in region.obj:
                nr = (csr.size + region.busword - 1)//region.busword
                r += _get_rw_functions_c(name + "_" + csr.name, origin, nr, region.busword, alignment,
                    getattr(csr, "read_only", False), with_access_functions)
                origin += alignment//8*nr
                if hasattr(csr, "fields"):
                    for field in csr.fields.fields:
                        offset = str(field.offset)
                        size = str(field.size)
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_OFFSET "+offset+"\n"
                        r += "#define CSR_"+name.upper()+"_"+csr.name.upper()+"_"+field.name.upper()+"_SIZE "+size+"\n"
                        if with_access_functions and csr.size <= 32: # FIXME: Implement extract/read functions for csr.size > 32-bit.
                            reg_name = name + "_" + csr.name.lower()
                            field_name = reg_name + "_" + field.name.lower()
                            r += "static inline uint32_t " + field_name + "_extract(uint32_t oldword) {\n"
                            r += "\tuint32_t mask = ((1 << " + size + ")-1);\n"
                            r += "\treturn ( (oldword >> " + offset + ") & mask );\n}\n"
                            r += "static inline uint32_t " + field_name + "_read(void) {\n"
                            r += "\tuint32_t word = " + reg_name + "_read();\n"
                            r += "\treturn " + field_name + "_extract(word);\n"
                            r += "}\n"
                            if not getattr(csr, "read_only", False):
                                r += "static inline uint32_t " + field_name + "_replace(uint32_t oldword, uint32_t plain_value) {\n"
                                r += "\tuint32_t mask = ((1 << " + size + ")-1);\n"
                                r += "\treturn (oldword & (~(mask << " + offset + "))) | (mask & plain_value)<< " + offset + " ;\n}\n"
                                r += "static inline void " + field_name + "_write(uint32_t plain_value) {\n"
                                r += "\tuint32_t oldword = " + reg_name + "_read();\n"
                                r += "\tuint32_t newword = " + field_name + "_replace(oldword, plain_value);\n"
                                r += "\t" + reg_name + "_write(newword);\n"
                                r += "}\n"

    r += "\n#endif\n"
    return r

# JSON Export --------------------------------------------------------------------------------------

def get_csr_json(csr_regions={}, constants={}, mem_regions={}):
    alignment = constants.get("CONFIG_CSR_ALIGNMENT", 32)

    d = {
        "csr_bases":     {},
        "csr_mem_sizes": {},
        "csr_registers": {},
        "constants":     {},
        "memories":      {},
    }

    for name, region in csr_regions.items():
        d["csr_bases"][name] = region.origin
        region_origin = region.origin
        if not isinstance(region.obj, Memory):
            for csr in region.obj:
                size = (csr.size + region.busword - 1)//region.busword
                d["csr_registers"][name + "_" + csr.name] = {
                    "addr": region_origin,
                    "size": size,
                    "type": "ro" if isinstance(csr, CSRStatus) else "rw"
                }
                region_origin += alignment//8*size
        else:
            mem = region.obj
            mem_sz = mem.width * mem.depth // 8
            d["csr_mem_sizes"][name] = mem_sz

    for name, value in constants.items():
        d["constants"][name.lower()] = value.lower() if isinstance(value, str) else value

    for name, region in mem_regions.items():
        d["memories"][name.lower()] = {
            "base": region.origin,
            "size": region.length,
            "type": region.type,
        }

    return json.dumps(d, indent=4)


# CSV Export --------------------------------------------------------------------------------------

def get_csr_csv(csr_regions={}, constants={}, mem_regions={}):
    d = json.loads(get_csr_json(csr_regions, constants, mem_regions))
    r = generated_banner("#")
    for name, value in d["csr_bases"].items():
        sz_str = ''
        if name in  d["csr_mem_sizes"]:
            sz_str = str(d["csr_mem_sizes"][name])
        r += "csr_base,{},0x{:08x},{},\n".format(name, value, sz_str)
    for name in d["csr_registers"].keys():
        r += "csr_register,{},0x{:08x},{},{}\n".format(name,
            d["csr_registers"][name]["addr"],
            d["csr_registers"][name]["size"],
            d["csr_registers"][name]["type"])
    for name, value in d["constants"].items():
        r += "constant,{},{},,\n".format(name, value)
    for name in d["memories"].keys():
        r += "memory_region,{},0x{:08x},{:d},{:s}\n".format(name,
            d["memories"][name]["base"],
            d["memories"][name]["size"],
            d["memories"][name]["type"],
            )
    return r

# SVD Export --------------------------------------------------------------------------------------

def get_csr_svd(soc, vendor="litex", name="soc", description=None):
    def sub_csr_bit_range(busword, csr, offset):
        nwords = (csr.size + busword - 1)//busword
        i = nwords - offset - 1
        nbits = min(csr.size - i*busword, busword) - 1
        name = (csr.name + str(i) if nwords > 1 else csr.name).upper()
        origin = i*busword
        return (origin, nbits, name)

    def print_svd_register(csr, csr_address, description, length, svd):
        svd.append('                <register>')
        svd.append('                    <name>{}</name>'.format(csr.short_numbered_name))
        if description is not None:
            svd.append('                    <description><![CDATA[{}]]></description>'.format(description))
        svd.append('                    <addressOffset>0x{:04x}</addressOffset>'.format(csr_address))
        svd.append('                    <resetValue>0x{:02x}</resetValue>'.format(csr.reset_value))
        svd.append('                    <size>{}</size>'.format(length))
        # svd.append('                    <access>{}</access>'.format(csr.access))  # 'access' is a lie: "read-only" registers can legitimately change state based on a write, and is in fact used to handle the "pending" field in events
        csr_address = csr_address + 4
        svd.append('                    <fields>')
        if hasattr(csr, "fields") and len(csr.fields) > 0:
            for field in csr.fields:
                svd.append('                        <field>')
                svd.append('                            <name>{}</name>'.format(field.name))
                svd.append('                            <msb>{}</msb>'.format(field.offset +
                                                                         field.size - 1))
                svd.append('                            <bitRange>[{}:{}]</bitRange>'.format(
                    field.offset + field.size - 1, field.offset))
                svd.append('                            <lsb>{}</lsb>'.format(field.offset))
                svd.append('                            <description><![CDATA[{}]]></description>'.format(
                    reflow(field.description)))
                svd.append('                        </field>')
        else:
            field_size = csr.size
            field_name = csr.short_name.lower()
            # Strip off "ev_" from eventmanager fields
            if field_name == "ev_enable":
                field_name = "enable"
            elif field_name == "ev_pending":
                field_name = "pending"
            elif field_name == "ev_status":
                field_name = "status"
            svd.append('                        <field>')
            svd.append('                            <name>{}</name>'.format(field_name))
            svd.append('                            <msb>{}</msb>'.format(field_size - 1))
            svd.append('                            <bitRange>[{}:{}]</bitRange>'.format(field_size - 1, 0))
            svd.append('                            <lsb>{}</lsb>'.format(0))
            svd.append('                        </field>')
        svd.append('                    </fields>')
        svd.append('                </register>')

    interrupts = {}
    for csr, irq in sorted(soc.irq.locs.items()):
        interrupts[csr] = irq

    documented_regions = []
    for region_name, region in soc.csr.regions.items():
        documented_regions.append(DocumentedCSRRegion(
            name           = region_name,
            region         = region,
            csr_data_width = soc.csr.data_width)
        )

    svd = []
    svd.append('<?xml version="1.0" encoding="utf-8"?>')
    svd.append('')
    svd.append('<device schemaVersion="1.1" xmlns:xs="http://www.w3.org/2001/XMLSchema-instance" xs:noNamespaceSchemaLocation="CMSIS-SVD.xsd" >')
    svd.append('    <vendor>{}</vendor>'.format(vendor))
    svd.append('    <name>{}</name>'.format(name.upper()))
    if description is not None:
        svd.append('    <description><![CDATA[{}]]></description>'.format(reflow(description)))
    else:
        fmt = "%Y-%m-%d %H:%M:%S"
        build_time = datetime.datetime.fromtimestamp(time.time()).strftime(fmt)
        svd.append('    <description><![CDATA[{}]]></description>'.format(reflow("Litex SoC " + build_time)))
    svd.append('')
    svd.append('    <addressUnitBits>8</addressUnitBits>')
    svd.append('    <width>32</width>')
    svd.append('    <size>32</size>')
    svd.append('    <access>read-write</access>')
    svd.append('    <resetValue>0x00000000</resetValue>')
    svd.append('    <resetMask>0xFFFFFFFF</resetMask>')
    svd.append('')
    svd.append('    <peripherals>')

    for region in documented_regions:
        csr_address = 0
        svd.append('        <peripheral>')
        svd.append('            <name>{}</name>'.format(region.name.upper()))
        svd.append('            <baseAddress>0x{:08X}</baseAddress>'.format(region.origin))
        svd.append('            <groupName>{}</groupName>'.format(region.name.upper()))
        if len(region.sections) > 0:
            svd.append('            <description><![CDATA[{}]]></description>'.format(
                reflow(region.sections[0].body())))
        svd.append('            <registers>')
        for csr in region.csrs:
            description = None
            if hasattr(csr, "description"):
                description = csr.description
            if isinstance(csr, _CompoundCSR) and len(csr.simple_csrs) > 1:
                is_first = True
                for i in range(len(csr.simple_csrs)):
                    (start, length, name) = sub_csr_bit_range(
                        region.busword, csr, i)
                    if length > 0:
                        bits_str = "Bits {}-{} of `{}`.".format(
                            start, start+length, csr.name)
                    else:
                        bits_str = "Bit {} of `{}`.".format(
                            start, csr.name)
                    if is_first:
                        if description is not None:
                            print_svd_register(
                                csr.simple_csrs[i], csr_address, bits_str + " " + description, length, svd)
                        else:
                            print_svd_register(
                                csr.simple_csrs[i], csr_address, bits_str, length, svd)
                        is_first = False
                    else:
                        print_svd_register(
                            csr.simple_csrs[i], csr_address, bits_str, length, svd)
                    csr_address = csr_address + 4
            else:
                length = ((csr.size + region.busword - 1) //
                            region.busword) * region.busword
                print_svd_register(
                    csr, csr_address, description, length, svd)
                csr_address = csr_address + 4
        svd.append('            </registers>')
        svd.append('            <addressBlock>')
        svd.append('                <offset>0</offset>')
        svd.append('                <size>0x{:x}</size>'.format(csr_address))
        svd.append('                <usage>registers</usage>')
        svd.append('            </addressBlock>')
        if region.name in interrupts:
            svd.append('            <interrupt>')
            svd.append('                <name>{}</name>'.format(region.name))
            svd.append('                <value>{}</value>'.format(interrupts[region.name]))
            svd.append('            </interrupt>')
        svd.append('        </peripheral>')
    svd.append('    </peripherals>')
    svd.append('    <vendorExtensions>')

    if len(soc.mem_regions) > 0:
        svd.append('        <memoryRegions>')
        for region_name, region in soc.mem_regions.items():
            svd.append('            <memoryRegion>')
            svd.append('                <name>{}</name>'.format(region_name.upper()))
            svd.append('                <baseAddress>0x{:08X}</baseAddress>'.format(region.origin))
            svd.append('                <size>0x{:08X}</size>'.format(region.size))
            svd.append('            </memoryRegion>')
        svd.append('        </memoryRegions>')

    svd.append('        <constants>')
    for name, value in soc.constants.items():
        svd.append('            <constant name="{}" value="{}" />'.format(name, value))
    svd.append('        </constants>')

    svd.append('    </vendorExtensions>')
    svd.append('</device>')
    return "\n".join(svd)


# Memory.x Export ----------------------------------------------------------------------------------

def get_memory_x(soc):
    r = get_linker_regions(soc.mem_regions)
    r += '\n'
    r += 'REGION_ALIAS("REGION_TEXT", spiflash);\n'
    r += 'REGION_ALIAS("REGION_RODATA", spiflash);\n'
    r += 'REGION_ALIAS("REGION_DATA", sram);\n'
    r += 'REGION_ALIAS("REGION_BSS", sram);\n'
    r += 'REGION_ALIAS("REGION_HEAP", sram);\n'
    r += 'REGION_ALIAS("REGION_STACK", sram);\n\n'
    r += '/* CPU reset location. */\n'
    r += '_stext = {:#08x};\n'.format(soc.cpu.reset_address)
    return r
