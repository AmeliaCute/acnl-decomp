"""
Configure ACNL decompilation project
Main script for project setup, symbol management, and file generation
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

from tools.scripts.extractor import ROMExtractor
from tools.scripts.function_manager import FunctionManager


def parse_ida_map(map_file: Path) -> List[Dict]:
    """
    Parse IDA MAP file and extract symbols
    
    Expected format:
     Start         Length     Name                   Class
     0000:00000000 000900000H ROM                    CODE
      Address         Publics by Value
     0000:00100000       sub_100000
     0000:00100024       sub_100024
    """
    symbols = []
    
    with open(map_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    in_publics_section = False
    
    for line in lines:
        stripped = line.strip()
        
        if "Publics by Value" in line:
            in_publics_section = True
            continue
        
        if not in_publics_section or not stripped:
            continue
        
        # Parse: " 0000:00100000       sub_100000"
        match = re.match(r'^\s*([0-9A-Fa-f]{4}):([0-9A-Fa-f]{8})\s+(\S+)', line)
        
        if match:
            offset = match.group(2)
            name = match.group(3)
            
            try:
                address = int(offset, 16)
                
                if any(name.startswith(prefix) for prefix in ["loc_", "locret_", "jpt_"]):
                    continue
                
                symbol_type = "function"
                if name.startswith("a") or any(name.startswith(prefix) for prefix in ["byte_", "dbl_", "def_", "flt_", "word_", "dword_", "qword_", "unk_", "off_", "stru_"]):
                    symbol_type = "data"
                
                symbols.append({
                    "address": address,
                    "name": name,
                    "type": symbol_type,
                    "size": 0,
                    "source_file": None,
                    "demangled": name
                })
                
            except ValueError:
                continue
    
    symbols.sort(key=lambda s: s["address"])
    
    for i in range(len(symbols) - 1):
        symbols[i]["size"] = symbols[i + 1]["address"] - symbols[i]["address"]
    
    return symbols


def assign_source_files(symbols: List[Dict]) -> List[Dict]:
    """
    Assign each symbol to a source file
    Strategy: One C file per function
    """
    for symbol in symbols:
        if symbol["type"] == "function":
            symbol["source_file"] = f"src/{symbol['name']}.c"
            symbol["header_file"] = "include/functions.h"
        else:
            symbol["source_file"] = f"src/data/{symbol['name']}.c"
            symbol["header_file"] = "include/data.h"
    
    return symbols


def create_symbols_json(symbols: List[Dict], output_file: Path):
    """Create the master symbols.json file"""
    
    functions = [s for s in symbols if s["type"] == "function"]
    data_symbols = [s for s in symbols if s["type"] == "data"]
    
    output = {
        "version": "1.0",
        "description": "Master symbol database for ACNL decompilation",
        "base_address": 0x00100000,
        "statistics": {
            "total_symbols": len(symbols),
            "functions": len(functions),
            "data": len(data_symbols),
        },
        "symbols": symbols
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"✓ Created {output_file}")
    print(f"  Total symbols: {len(symbols)}")
    print(f"  Functions: {len(functions)}")
    print(f"  Data: {len(data_symbols)}")


def import_symbols_from_map(map_file: Path, output_file: Path):
    """Import symbols from IDA MAP file"""
    if not map_file.exists():
        print(f"ERROR: Map file not found: {map_file}")
        sys.exit(1)
    
    print(f"Reading IDA MAP file: {map_file}")
    symbols = parse_ida_map(map_file)
    
    if not symbols:
        print("ERROR: No symbols found in MAP file")
        print("Make sure the MAP file contains a 'Publics by Value' section")
        sys.exit(1)
    
    print(f"Found {len(symbols)} symbols")
    
    print("Assigning source files...")
    symbols = assign_source_files(symbols)
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    create_symbols_json(symbols, output_file)


def load_symbols(symbols_file: Path) -> Dict:
    """Load symbols.json"""
    with open(symbols_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_source_files(symbols: List[Dict], root_dir: Path):
    """Generate C source files for each function"""
    src_dir = root_dir / "src"
    data_dir = src_dir / "data"
    src_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)
    
    functions = [s for s in symbols if s["type"] == "function"]
    
    created_count = 0
    for symbol in functions:
        source_file = root_dir / str(symbol["source_file"])
        source_file.parent.mkdir(parents=True, exist_ok=True)
        
        if source_file.exists():
            continue
        
        content = f"""/*
 * {symbol['name']}.c
 * Auto-generated from symbols.json
 * 
 * Address: 0x{symbol['address']:08X}
 * Size: 0x{symbol['size']:X} bytes
 */

#include "functions.h"

// {symbol['demangled']}
void {symbol['name']}(void) {{
    // TODO: Decompile this function
}}
"""
        
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(content)
        created_count += 1
    
    print(f"✓ Generated {created_count} source files in {src_dir}/")


def generate_function_header(symbols: List[Dict], root_dir: Path):
    """Generate functions.h with all function declarations"""
    include_dir = root_dir / "include"
    include_dir.mkdir(exist_ok=True)
    
    header_file = include_dir / "functions.h"
    
    functions = sorted([s for s in symbols if s["type"] == "function"], key=lambda s: s["address"])
    
    content = """/*
 * functions.h
 * Auto-generated from symbols.json
 * All function declarations
 */

#ifndef FUNCTIONS_H
#define FUNCTIONS_H

#include <stdint.h>

"""
    
    for symbol in functions:
        content += f"// 0x{symbol['address']:08X} - {symbol['demangled']}\n"
        content += f"void {symbol['name']}(void);\n\n"
    
    content += "#endif /* FUNCTIONS_H */\n"
    
    with open(header_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Generated {header_file}")


def generate_data_header(symbols: List[Dict], root_dir: Path):
    """Generate data.h with all data declarations"""
    include_dir = root_dir / "include"
    include_dir.mkdir(exist_ok=True)
    
    header_file = include_dir / "data.h"
    
    data_symbols = sorted([s for s in symbols if s["type"] == "data"], key=lambda s: s["address"])
    
    if not data_symbols:
        return
    
    content = """/*
 * data.h
 * Auto-generated from symbols.json
 * All data declarations
 */

#ifndef DATA_H
#define DATA_H

#include <stdint.h>

"""
    
    for symbol in data_symbols:
        content += f"// 0x{symbol['address']:08X}\n"
        content += f"extern uint8_t {symbol['name']}[];\n\n"
    
    content += "#endif /* DATA_H */\n"
    
    with open(header_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Generated {header_file}")


def generate_linker_script(symbols: List[Dict], root_dir: Path):
    """Generate linker.ld with symbol addresses"""
    linker_file = root_dir / "linker.ld"
    
    content = """/*
 * linker.ld
 * Auto-generated from symbols.json
 */

OUTPUT_FORMAT("elf32-littlearm", "elf32-bigarm", "elf32-littlearm")
OUTPUT_ARCH(arm)
ENTRY(_start)

MEMORY {
    CODE : ORIGIN = 0x00100000, LENGTH = 8M
}

SECTIONS {
    .text 0x00100000 : {
        *(.text .text.*)
        *(.rodata .rodata.*)
    } > CODE

    .data : {
        *(.data .data.*)
    } > CODE

    .bss : {
        *(.bss .bss.*)
        *(COMMON)
    } > CODE

    /* Symbol addresses */
"""
    
    for symbol in sorted(symbols, key=lambda s: s["address"]):
        content += f"    {symbol['name']} = 0x{symbol['address']:08X};\n"
    
    content += "}\n"
    
    with open(linker_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Generated {linker_file}")


def generate_ninja_build(symbols: List[Dict], root_dir: Path):
    """Generate build.ninja"""
    build_file = root_dir / "build.ninja"
    
    functions = [s for s in symbols if s["type"] == "function"]
    
    content = """# build.ninja
# Auto-generated from symbols.json

CC = arm-none-eabi-gcc
AS = arm-none-eabi-as
LD = arm-none-eabi-ld
OBJCOPY = arm-none-eabi-objcopy

CFLAGS = -g -O2 -marm -mcpu=mpcore -mfpu=vfp -mfloat-abi=softfp -Wall -Iinclude
LDFLAGS = -T linker.ld

rule cc
  command = $CC $CFLAGS -c $in -o $out
  description = CC $out

rule ld
  command = $LD $LDFLAGS @$out.rsp -o $out
  description = LINK $out
  rspfile = $out.rsp
  rspfile_content = $in
  
rule objcopy
  command = $OBJCOPY -O binary $in $out
  description = OBJCOPY $out

"""
    
    obj_files = []
    for symbol in functions:
        src_path = symbol["source_file"]
        obj_path = f"build/{symbol['name']}.o"
        obj_files.append(obj_path)
        
        content += f"build {obj_path}: cc {src_path}\n"
    
    content += f"\nbuild build/code.elf: ld {' '.join(obj_files)}\n"
    content += "build build/code.bin: objcopy build/code.elf\n"
    
    with open(build_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Generated {build_file}")


def generate_objdiff_config(symbols: List[Dict], root_dir: Path, region: str):
    """Generate objdiff.json with correct paths"""
    objdiff_file = root_dir / "objdiff.json"
    
    functions = [s for s in symbols if s["type"] == "function"]
    
    units = []
    for symbol in functions:
        unit = {
            "name": symbol['name'],
            "target_path": f"build/asm/{symbol['name']}.o",
            "base_path": f"build/{symbol['name']}.o",
            "metadata": {
                "complete": False,
                "mapped": True,
                "source_path": symbol["source_file"]
            }
        }
        units.append(unit)
    
    config = {
        "$schema": "https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json",
        "custom_make": "ninja",
        "build_target": True,
        "watch_patterns": ["src/**/*.c", "include/**/*.h"],
        "units": units,
        "map_file": "symbols/symbols.txt"
    }
    
    with open(objdiff_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Generated {objdiff_file}")


def generate_symbol_map(symbols: List[Dict], root_dir: Path):
    """Generate symbol map file in format objdiff expects"""
    symbols_dir = root_dir / "symbols"
    symbols_dir.mkdir(exist_ok=True)
    
    map_file = symbols_dir / "symbols.txt"
    
    with open(map_file, 'w', encoding='utf-8') as f:
        # Write in format: address type name
        for symbol in sorted(symbols, key=lambda s: s["address"]):
            type_char = 'T' if symbol["type"] == "function" else 'D'
            # Format: 00100000 T start
            f.write(f"{symbol['address']:08x} {type_char} {symbol['name']}\n")
    
    print(f"✓ Generated {map_file}")
    

def inject_symbols_to_elf(symbols: List[Dict], root_dir: Path, region: str):
    """
    Creates a proper ELF with symbols that objdiff can parse.
    Simple two-step approach: create ELF, then add symbols to section.
    """
    origin_dir = root_dir / "origin" / region
    code_bin = origin_dir / "code.bin"
    code_elf = origin_dir / "code.elf"
    
    if not code_bin.exists():
        print(f"ERROR: {code_bin} not found")
        return
    
    base_address = 0x00100000
    code_size = code_bin.stat().st_size
    
    print(f"Creating ELF with symbols from {code_bin}...")
    print(f"  Binary size: 0x{code_size:x} bytes ({code_size / 1024 / 1024:.2f} MB)")
    
    build_dir = root_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    print("Step 1: Converting binary to ELF...")
    
    try:
        subprocess.run([
            "arm-none-eabi-objcopy",
            "--input-target=binary",
            "--output-target=elf32-littlearm",
            "--binary-architecture=arm",
            f"--change-section-address=.data={base_address:#x}",
            "--rename-section=.data=.text,alloc,load,readonly,code,contents",
            str(code_bin),
            str(code_elf)
        ], check=True, capture_output=True)
        print("✓ Created base ELF")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create ELF: {e}")
        if e.stderr:
            print(f"  {e.stderr.decode()}")
        return
    
    # Step 2: Remove auto-generated symbols
    print("Step 2: Cleaning auto-generated symbols...")
    
    try:
        subprocess.run([
            "arm-none-eabi-strip",
            "--strip-symbol=_binary_origin_EGDP_code_bin_start",
            "--strip-symbol=_binary_origin_EGDP_code_bin_end",
            "--strip-symbol=_binary_origin_EGDP_code_bin_size",
            str(code_elf)
        ], check=True, capture_output=True)
        print("✓ Removed auto-generated symbols")
    except subprocess.CalledProcessError:
        # Might not exist, that's OK
        pass
    
    # Step 3: Add our symbols in small batches
    print(f"Step 3: Adding {len(symbols)} symbols...")
    
    # Sort symbols by address
    sorted_symbols = sorted([s for s in symbols if s.get("name") and isinstance(s.get("address"), int)], key=lambda s: s['address'])
    
    # Process in batches of 25 to avoid command line limits
    batch_size = 25
    total_batches = (len(sorted_symbols) + batch_size - 1) // batch_size
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(sorted_symbols))
        batch = sorted_symbols[start_idx:end_idx]
        
        cmd = ["arm-none-eabi-objcopy"]
        
        for sym in batch:
            name = sym["name"]
            addr = sym["address"]
            sym_type = sym.get("type", "function")
            
            # Calculate offset from base address
            offset = addr - base_address
            
            # Determine symbol type flags
            if sym_type == "function":
                flags = "function,global"
            else:
                flags = "object,global"
            
            # Add symbol at section offset
            cmd.append("--add-symbol")
            cmd.append(f"{name}=.text:0x{offset:x},{flags}")
        
        cmd.append(str(code_elf))
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to add symbols (batch {batch_num + 1}/{total_batches}): {e}")
            if e.stderr:
                stderr = e.stderr.decode()
                print(f"  {stderr}")
            continue
        
        # Progress indicator
        if (batch_num + 1) % 10 == 0 or batch_num == total_batches - 1:
            print(f"  Progress: {batch_num + 1}/{total_batches} batches ({end_idx}/{len(sorted_symbols)} symbols)")
    
    print("✓ Added all symbols")
    
    # Step 4: Verify the result
    print("Step 4: Verifying ELF...")
    
    try:
        # Check sections
        result = subprocess.run(
            ["arm-none-eabi-objdump", "-h", str(code_elf)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("\nSection info:")
            for line in result.stdout.split('\n'):
                if '.text' in line and 'CONTENTS' in line:
                    print(f"  {line.strip()}")
                    
                    # Parse and check VMA/LMA
                    parts = line.split()
                    try:
                        if '.text' in parts:
                            idx = parts.index('.text')
                            if idx + 3 < len(parts):
                                vma = parts[idx + 2]
                                lma = parts[idx + 3]
                                if vma != lma:
                                    print(f"\n  ⚠ WARNING: VMA ({vma}) != LMA ({lma})")
                                    print("     Objdiff may have issues. Attempting fix...")
                                    
                                    # Fix LMA
                                    subprocess.run([
                                        "arm-none-eabi-objcopy",
                                        f"--change-section-lma=.text={base_address:#x}",
                                        str(code_elf)
                                    ], check=True, capture_output=True)
                                    
                                    print("  ✓ Fixed LMA")
                    except (ValueError, IndexError):
                        pass
                    
                    break
        
        # Check symbols
        result = subprocess.run(
            ["arm-none-eabi-nm", "-n", str(code_elf)],
            capture_output=True,
            text=True,
            check=True
        )
        
        symbol_lines = [line for line in result.stdout.split('\n') if line.strip() and 'T ' in line]
        print(f"\n✓ Verified {len(symbol_lines)} function symbols in ELF")
        
        if symbol_lines:
            print("\nFirst 10 symbols:")
            for line in symbol_lines[:10]:
                print(f"  {line}")
                
    except subprocess.CalledProcessError:
        print("WARNING: Could not verify ELF")
    except FileNotFoundError:
        print("WARNING: Verification tools not found")
    
    print(f"\n✓ ELF creation complete: {code_elf}")


def split_elf_to_objects(symbols: List[Dict], root_dir: Path, region: str):
    """
    Split the main ELF into individual .o files for each function.
    Each function starts at offset 0 in its own .o file.
    """
    origin_dir = root_dir / "origin" / region
    code_elf = origin_dir / "code.elf"
    
    if not code_elf.exists():
        print(f"ERROR: {code_elf} not found")
        return
    
    build_dir = root_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a subdirectory for target objects
    target_dir = build_dir / "asm"
    target_dir.mkdir(exist_ok=True)
    
    base_address = 0x00100000
    
    # Get only functions, sorted by address
    functions = sorted([s for s in symbols if s.get("type") == "function"], key=lambda s: s["address"])
    
    print(f"\nSplitting ELF into {len(functions)} individual .o files...")
    
    # First, extract the entire .text section once
    full_text_bin = build_dir / "full_text.bin"
    try:
        subprocess.run([
            "arm-none-eabi-objcopy",
            "-O", "binary",
            "--only-section=.text",
            str(code_elf),
            str(full_text_bin)
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to extract .text section: {e}")
        return
    
    # Read the entire .text section into memory
    try:
        with open(full_text_bin, 'rb') as f:
            full_text_data = f.read()
        text_size = len(full_text_data)
        print(f"Extracted .text section: {text_size} bytes (0x{text_size:x})")
    except Exception as e:
        print(f"ERROR: Failed to read .text section: {e}")
        return
    
    created_count = 0
    failed_count = 0
    
    for i, func in enumerate(functions):
        name = func["name"]
        addr = func["address"]
        size = func.get("size", 0)
        
        # If size is 0, calculate from next function
        if size == 0 and i < len(functions) - 1:
            size = functions[i + 1]["address"] - addr
        elif size == 0:
            # Last function, use remaining bytes
            size = (base_address + text_size) - addr
        
        # Calculate file offset from base address
        offset = addr - base_address
        
        # Validate offset and size
        if offset < 0 or offset >= text_size:
            if failed_count < 5:
                print(f"  WARNING: {name} offset 0x{offset:x} is out of bounds (text size: 0x{text_size:x})")
            failed_count += 1
            continue
        
        if offset + size > text_size:
            old_size = size
            size = text_size - offset
            if failed_count < 5:
                print(f"  WARNING: {name} size truncated from 0x{old_size:x} to 0x{size:x}")
        
        if size <= 0:
            if failed_count < 5:
                print(f"  WARNING: {name} has invalid size {size}")
            failed_count += 1
            continue
        
        # Output object file
        obj_file = target_dir / f"{name}.o"
        
        try:
            # Step 1: Extract this function's bytes from the full text data
            func_bytes = full_text_data[offset:offset + size]
            
            if len(func_bytes) != size:
                print(f"  WARNING: {name} extracted {len(func_bytes)} bytes, expected {size}")
            
            # Step 2: Write to a temporary binary file
            func_bin = build_dir / f"{name}_func.bin"
            with open(func_bin, 'wb') as f:
                f.write(func_bytes)
            
            # Step 3: Convert binary to ELF object
            # This creates .data section with the binary data
            subprocess.run([
                "arm-none-eabi-objcopy",
                "-I", "binary",
                "-O", "elf32-littlearm",
                "-B", "arm",
                str(func_bin),
                str(obj_file)
            ], check=True, capture_output=True)
            
            # Step 4: Rename .data to .text and set proper flags with correct alignment
            subprocess.run([
                "arm-none-eabi-objcopy",
                "--rename-section", ".data=.text,alloc,load,readonly,code,contents",
                "--set-section-alignment", ".text=2",  # 2^2 = 4 bytes
                str(obj_file)
            ], check=True, capture_output=True)
            
            # Step 5: Strip ALL symbols, then add only our function symbol at offset 0
            subprocess.run([
                "arm-none-eabi-strip",
                "--strip-all",
                str(obj_file)
            ], check=True, capture_output=True)
            
            # Step 6: Add our function symbol at offset 0
            subprocess.run([
                "arm-none-eabi-objcopy",
                "--add-symbol", f"{name}=.text:0,function,global",
                str(obj_file)
            ], check=True, capture_output=True)
            
            created_count += 1
            
            # Clean up temp file
            func_bin.unlink(missing_ok=True)
            
            # Progress indicator
            if (i + 1) % 50 == 0 or i == len(functions) - 1:
                print(f"  Progress: {i + 1}/{len(functions)} functions extracted")
            
        except subprocess.CalledProcessError as e:
            failed_count += 1
            if failed_count <= 5:  # Only show first few errors
                print(f"  WARNING: Failed to extract {name}: {e}")
                if hasattr(e, 'stderr') and e.stderr:
                    print(f"    {e.stderr.decode()}")
        except Exception as e:
            failed_count += 1
            if failed_count <= 5:
                print(f"  WARNING: Error processing {name}: {e}")
    
    # Clean up the full text binary
    full_text_bin.unlink(missing_ok=True)
    
    print(f"\n✓ Created {created_count} object files in {target_dir}/")
    if failed_count > 0:
        print(f"  ⚠ {failed_count} functions failed to extract")
    
    # Verify a few objects
    if created_count > 0 and len(functions) > 0:
        print("\nVerifying first object file...")
        # Find the first successfully created object
        first_func = None
        for func in functions:
            obj_path = target_dir / f"{func['name']}.o"
            if obj_path.exists():
                first_func = func
                break
        
        if first_func:
            first_obj = target_dir / f"{first_func['name']}.o"
            try:
                result = subprocess.run(
                    ["arm-none-eabi-objdump", "-t", str(first_obj)],
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"  Symbol table for {first_func['name']}:")
                for line in result.stdout.split('\n'):
                    if first_func['name'] in line or '.text' in line:
                        print(f"    {line}")
            except Exception:
                pass


def generate_diff_settings(root_dir: Path, region: str):
    """Generate diff_settings.py for objdiff tool"""
    diff_settings = root_dir / "diff_settings.py"
    
    content = """
import os


def apply(config):
    config["arch"] = "arm"
    config["arch_objdump"] = "arm"
    config["platform"] = "3ds"
    config["base_addr"] = 0x00100000

    config["source_directories"] = [
        "src",
        "include",
    ]

    config["objdump_executable"] = os.environ.get('DEVKITARM') + "/bin/arm-none-eabi-objdump"
    
    config["show_line_numbers"] = True
    config["show_branch_targets"] = True
    config["show_data_refs"] = True
    
    config["colors"] = {{
        "match": "#00FF00",
        "mismatch": "#FF0000",
        "missing": "#FFFF00",
    }}
"""
    
    with open(diff_settings, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print(f"✓ Generated {diff_settings}")


def generate_project(root_dir: Path, region: str):
    """Generate all project files from symbols.json"""
    symbols_file = root_dir / "symbols" / "symbols.json"
    
    if not symbols_file.exists():
        print("ERROR: symbols/symbols.json not found")
        print("Use --import-symbols <map_file> to create it first")
        sys.exit(1)
    
    tools_dir = root_dir / "tools"
    origin_dir = root_dir / "origin" / region
    extractor = ROMExtractor(tools_dir, origin_dir, origin_dir)
    
    if not extractor.verify_rom_exists():
        print(f"No ROM found in {origin_dir}")
        print("Please place your .3ds or .cia file in the appropriate origin directory")
        return 1
    
    try:
        extractor.extract()
        print("✓ ROM extraction complete")
        
    except Exception as e:
        print(f"ROM extraction failed: {e}")
        return 1
    
    print("=" * 32)
    print("Generating project from symbols.json")
    print("=" * 32)
    
    data = load_symbols(symbols_file)
    symbols = data["symbols"]
    
    print(f"Loaded {len(symbols)} symbols")
    
    print("Generating source files...")
    generate_source_files(symbols, root_dir)
    
    print("Generating headers...")
    generate_function_header(symbols, root_dir)
    generate_data_header(symbols, root_dir)
    
    print("Generating build files...")
    generate_linker_script(symbols, root_dir)
    generate_ninja_build(symbols, root_dir)
    generate_objdiff_config(symbols, root_dir, region)
    
    print("Generating documentation...")
    generate_symbol_map(symbols, root_dir)
    inject_symbols_to_elf(symbols, root_dir, region)
    split_elf_to_objects(symbols, root_dir, region)
    generate_diff_settings(root_dir, region)
    
    print("=" * 32)
    print("✓ Generation complete!")
    print("=" * 32)
    print(f"Source files: {len([s for s in symbols if s['type'] == 'function'])}")
    print("Build with: ninja")
    print("Compare with: objdiff")


def main():
    parser = argparse.ArgumentParser(
        description="Configure ACNL decompilation project", 
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import symbols and generate project
  python configure.py --import-symbols code.bin.map
  
  # Add a new function
  python configure.py --add-function sub_123456 --address 0x123456
  
  # Rename a function
  python configure.py --rename-function sub_123456 --to GameLoop_Update
  
  # Regenerate all project files (including missing source files)
  python configure.py --regenerate
        """
    )
    
    parser.add_argument("--import-symbols", type=str, metavar="MAP_FILE", help="Import symbols from IDA MAP file")
    parser.add_argument("--region", type=str, default="EGDP", help="Game region (default: EGDP)")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate all project files from symbols.json")
    
    parser.add_argument("--add-function", type=str, metavar="NAME", help="Add a new function")
    parser.add_argument("--address", type=str, metavar="ADDRESS", help="Function address (required with --add-function)")
    parser.add_argument("--size", type=str, default="0", metavar="SIZE", help="Function size (optional)")
    parser.add_argument("--rename-function", type=str, metavar="OLD_NAME", help="Rename an existing function")
    parser.add_argument("--to", type=str, metavar="NEW_NAME", help="New function name (required with --rename-function)")
    
    args = parser.parse_args()
    
    root_dir = Path(".")
    symbols_file = root_dir / "symbols" / "symbols.json"
    
    if args.import_symbols:
        map_file = Path(args.import_symbols)
        print("=" * 32)
        print("STEP 1: Importing symbols from MAP file")
        print("=" * 32)
        import_symbols_from_map(map_file, symbols_file)
        print()
    
    if args.add_function or args.rename_function:
        if not symbols_file.exists():
            print("ERROR: No symbols.json found")
            print("Run with --import-symbols first")
            sys.exit(1)
        
        func_manager = FunctionManager(root_dir, args.region)
        
        if args.add_function and args.address:
            try:
                address_str = args.address.replace("0x", "").replace("0X", "")
                address = int(address_str, 16)
                size_str = args.size.replace("0x", "").replace("0X", "")
                size = int(size_str, 16)
            except ValueError as e:
                print(f"ERROR: Invalid address or size format: {e}")
                sys.exit(1)
            
            func_manager.add_function(args.add_function, address, size)
            print()
            
        elif args.rename_function and args.to:
            func_manager.rename_function(args.rename_function, args.to)
            print()
            
        else:
            print("ERROR: Invalid function operation arguments")
            if args.add_function:
                print("  --add-function requires --address")
            if args.rename_function:
                print("  --rename-function requires --to")
            sys.exit(1)
    
    elif args.regenerate or symbols_file.exists():
        print("=" * 32)
        print("Generating project files")
        print("=" * 32)
        generate_project(root_dir, args.region)
    else:
        print("ERROR: No symbols.json found and no MAP file provided")
        print("Use --import-symbols <map_file> to import symbols first")
        print("Example:")
        print("  python configure.py --import-symbols origin/EGDP/code.bin.map")
        sys.exit(1)


if __name__ == "__main__":
    main()