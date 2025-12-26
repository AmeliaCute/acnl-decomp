"""
function_manager.py - Module for adding and renaming functions

This module provides functionality to add or rename functions in all necessary files:
- symbols.json
- C source file
- functions.h header
- linker.ld
- build.ninja
- objdiff.json
"""

import json
import sys
from pathlib import Path
from typing import Dict, Optional


class FunctionManager:
    def __init__(self, root_dir: Path, region: str):
        self.root_dir = root_dir
        self.region = region
        self.symbols_file = root_dir / "symbols" / "symbols.json"
        
    def load_symbols(self) -> Dict:
        """Load symbols.json"""
        if not self.symbols_file.exists():
            print(f"ERROR: {self.symbols_file} not found")
            print("Run configure.py first to create the project")
            sys.exit(1)
            
        with open(self.symbols_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_symbols(self, data: Dict):
        """Save symbols.json"""
        with open(self.symbols_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def find_symbol_by_name(self, data: Dict, name: str) -> Optional[Dict]:
        """Find a symbol by name"""
        for symbol in data['symbols']:
            if symbol['name'] == name:
                return symbol
        return None
    
    def function_exists(self, data: Dict, name: str, address: int) -> bool:
        """Check if function already exists by name or address"""
        for symbol in data['symbols']:
            if symbol['name'] == name:
                return True
            if symbol['address'] == address:
                print(f"ERROR: Address 0x{address:08X} already occupied by '{symbol['name']}'")
                return True
        return False
    
    def add_to_symbols_json(self, name: str, address: int, size: int = 0) -> Dict:
        """Add function to symbols.json"""
        print("[1/6] Adding to symbols.json...")
        
        data = self.load_symbols()

        existing = self.find_symbol_by_name(data, name)
        if existing:
            print(f"   ⚠ Function '{name}' already exists in symbols.json")
            return existing
        
        for symbol in data['symbols']:
            if symbol['address'] == address:
                print(f"ERROR: Address 0x{address:08X} already occupied by '{symbol['name']}'")
                sys.exit(1)
        
        new_symbol = {
            "address": address,
            "name": name,
            "type": "function",
            "size": size,
            "source_file": f"src/{name}.c",
            "demangled": name
        }
        
        data['symbols'].append(new_symbol)
        data['symbols'].sort(key=lambda s: s['address'])
        
        data['statistics']['total_symbols'] = len(data['symbols'])
        data['statistics']['functions'] = len([s for s in data['symbols'] if s['type'] == 'function'])
        
        for i in range(len(data['symbols']) - 1):
            data['symbols'][i]['size'] = data['symbols'][i + 1]['address'] - data['symbols'][i]['address']
        
        self.save_symbols(data)
        print(f"   ✓ Added {name} at 0x{address:08X}")
        
        return new_symbol
    
    def create_source_file(self, symbol: Dict):
        """Create C source file for the function"""
        print("[2/6] Creating source file...")
        
        source_file = self.root_dir / "src" / f"{symbol['name']}.c"
        
        if source_file.exists():
            print(f"   ⚠ {source_file} already exists, skipping")
            return
        
        source_file.parent.mkdir(parents=True, exist_ok=True)
        
        content = f"""/*
 * {symbol['name']}.c
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
        
        print(f"   ✓ Created {source_file}")
    
    def update_functions_header(self, symbol: Dict):
        """Add function declaration to functions.h"""
        print("[3/6] Updating functions.h...")
        
        header_file = self.root_dir / "include" / "functions.h"
        
        if not header_file.exists():
            print(f"   ERROR: {header_file} not found")
            sys.exit(1)
        
        with open(header_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        declaration = f"void {symbol['name']}(void);"
        if declaration in content:
            print("   ⚠ Function already declared in header")
            return
        
        new_declaration = f"// 0x{symbol['address']:08X} - {symbol['demangled']}\nvoid {symbol['name']}(void);\n\n"
        
        if "#endif" in content:
            parts = content.rsplit("#endif", 1)
            new_content = parts[0] + new_declaration + "#endif" + parts[1]
        else:
            new_content = content + new_declaration
        
        with open(header_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   ✓ Updated {header_file}")
    
    def update_linker_script(self, symbol: Dict):
        """Add symbol address to linker.ld"""
        print("[4/6] Updating linker.ld...")
        
        linker_file = self.root_dir / "linker.ld"
        
        if not linker_file.exists():
            print(f"   ERROR: {linker_file} not found")
            sys.exit(1)
        
        with open(linker_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        symbol_def = f"{symbol['name']} = 0x{symbol['address']:08X}"
        if symbol_def in content:
            print("   ⚠ Symbol already in linker script")
            return
        
        symbol_line = f"    {symbol['name']} = 0x{symbol['address']:08X};\n"
        
        if content.rstrip().endswith('}'):
            new_content = content.rstrip()[:-1] + symbol_line + "}\n"
        else:
            new_content = content + symbol_line
        
        with open(linker_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   ✓ Updated {linker_file}")
    
    def update_ninja_build(self, symbol: Dict):
        """Add build rule to build.ninja"""
        print("[5/6] Updating build.ninja...")
        
        build_file = self.root_dir / "build.ninja"
        
        if not build_file.exists():
            print(f"   ERROR: {build_file} not found")
            sys.exit(1)
        
        with open(build_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        obj_path = f"build/{symbol['name']}.o"
        src_path = symbol['source_file']
        
        if f"build {obj_path}:" in content:
            print("   ⚠ Build rule already exists")
            return
        
        build_rule = f"build {obj_path}: cc {src_path}\n"
        
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            if line.startswith('build build/code.elf: ld'):
                if obj_path not in line:
                    line = line.rstrip() + f" {obj_path}"
            new_lines.append(line)
        
        for i, line in enumerate(new_lines):
            if line.startswith('build build/code.elf:'):
                new_lines.insert(i, build_rule)
                break
        
        new_content = '\n'.join(new_lines)
        
        with open(build_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"   ✓ Updated {build_file}")
    
    def update_objdiff_config(self, symbol: Dict):
        """Add unit to objdiff.json"""
        print("[6/6] Updating objdiff.json...")
        
        objdiff_file = self.root_dir / "objdiff.json"
        
        if not objdiff_file.exists():
            print(f"   ERROR: {objdiff_file} not found")
            sys.exit(1)
        
        with open(objdiff_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        unit_name = f"main/ACNL/{symbol['name']}"
        for unit in config.get('units', []):
            if unit['name'] == unit_name:
                print("   ⚠ Unit already in objdiff.json")
                return
        
        new_unit = {
            "name": unit_name,
            "target_path": f"origin/{self.region}/code.bin",
            "base_path": f"build/{symbol['name']}.o",
            "metadata": {
                "address": f"0x{symbol['address']:08X}",
                "size": symbol['size'],
                "source_path": symbol['source_file']
            }
        }
        
        if 'units' not in config:
            config['units'] = []
        
        config['units'].append(new_unit)
        config['units'].sort(key=lambda u: int(u['metadata']['address'], 16))
        
        with open(objdiff_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print(f"   ✓ Updated {objdiff_file}")
    
    def add_function(self, name: str, address: int, size: int = 0):
        """Add a new function to all project files"""
        print("=" * 32)
        print(f"Adding function: {name}")
        print(f"Address: 0x{address:08X}")
        print(f"Size: 0x{size:X} bytes" if size > 0 else "Size: Unknown (will calculate)")
        print("=" * 32)
        print()
        
        symbol = self.add_to_symbols_json(name, address, size)
        self.create_source_file(symbol)
        self.update_functions_header(symbol)
        self.update_linker_script(symbol)
        self.update_ninja_build(symbol)
        self.update_objdiff_config(symbol)
        
        print()
        print("=" * 32)
        print("✓ Function added successfully!")
        print("=" * 32)
        print()
        print(f"  1. Edit src/{name}.c to implement the function")
        print("  2. Run 'ninja' to build")
        print("  3. Use objdiff to compare with original")
    
    def rename_function(self, old_name: str, new_name: str):
        """Rename a function in all project files"""
        print("=" * 32)
        print(f"Renaming function: {old_name} -> {new_name}")
        print("=" * 32)
        print()
        
        data = self.load_symbols()
        symbol = self.find_symbol_by_name(data, old_name)
        
        if not symbol:
            print(f"ERROR: Function '{old_name}' not found")
            sys.exit(1)
        
        if symbol['type'] != 'function':
            print(f"ERROR: '{old_name}' is not a function (type: {symbol['type']})")
            sys.exit(1)
        
        if self.find_symbol_by_name(data, new_name):
            print(f"ERROR: Function '{new_name}' already exists")
            sys.exit(1)
        
        old_source_file = self.root_dir / symbol['source_file']
        new_source_file = self.root_dir / f"src/{new_name}.c"
        
        print("[1/6] Updating symbols.json...")
        symbol['name'] = new_name
        symbol['source_file'] = f"src/{new_name}.c"
        symbol['demangled'] = new_name
        self.save_symbols(data)
        print("   ✓ Updated symbol name")
        
        print("[2/6] Renaming source file...")
        if old_source_file.exists():
            with open(old_source_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            content = content.replace(f"{old_name}.c", f"{new_name}.c")
            content = content.replace(f"void {old_name}(", f"void {new_name}(")
            
            with open(new_source_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            old_source_file.unlink()
            print(f"   ✓ Renamed {old_source_file.name} -> {new_source_file.name}")
        else:
            print(f"   ⚠ Source file {old_source_file} not found, creating new one")
            self.create_source_file(symbol)
        
        print("[3/6] Updating functions.h...")
        self._replace_in_header(old_name, new_name)
        
        print("[4/6] Updating linker.ld...")
        self._replace_in_linker(old_name, new_name)
        
        print("[5/6] Updating build.ninja...")
        self._replace_in_ninja(old_name, new_name)
        
        print("[6/6] Updating objdiff.json...")
        self._replace_in_objdiff(old_name, new_name)
        
        print()
        print("=" * 32)
        print("✓ Function renamed successfully!")
        print("=" * 32)
        print()
        print("Next steps:")
        print(f"  1. Review src/{new_name}.c")
        print("  2. Run 'ninja' to rebuild")
        print("  3. Use objdiff to verify")
    
    def _replace_in_header(self, old_name: str, new_name: str):
        """Replace function name in functions.h"""
        header_file = self.root_dir / "include" / "functions.h"
        
        if not header_file.exists():
            print(f"   ERROR: {header_file} not found")
            sys.exit(1)
        
        with open(header_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace(f"void {old_name}(void);", f"void {new_name}(void);")
        
        with open(header_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✓ Updated {header_file}")
    
    def _replace_in_linker(self, old_name: str, new_name: str):
        """Replace symbol name in linker.ld"""
        linker_file = self.root_dir / "linker.ld"
        
        if not linker_file.exists():
            print(f"   ERROR: {linker_file} not found")
            sys.exit(1)
        
        with open(linker_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if f"{old_name} = 0x" in line:
                line = line.replace(old_name, new_name)
            new_lines.append(line)
        
        with open(linker_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        
        print(f"   ✓ Updated {linker_file}")
    
    def _replace_in_ninja(self, old_name: str, new_name: str):
        """Replace build rules in build.ninja"""
        build_file = self.root_dir / "build.ninja"
        
        if not build_file.exists():
            print(f"   ERROR: {build_file} not found")
            sys.exit(1)
        
        with open(build_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace(f"build/{old_name}.o", f"build/{new_name}.o")
        content = content.replace(f"src/{old_name}.c", f"src/{new_name}.c")
        
        with open(build_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"   ✓ Updated {build_file}")
    
    def _replace_in_objdiff(self, old_name: str, new_name: str):
        """Replace unit name in objdiff.json"""
        objdiff_file = self.root_dir / "objdiff.json"
        
        if not objdiff_file.exists():
            print(f"   ERROR: {objdiff_file} not found")
            sys.exit(1)
        
        with open(objdiff_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        for unit in config.get('units', []):
            if old_name in unit['name']:
                unit['name'] = f"main/ACNL/{new_name}"
                unit['base_path'] = f"build/{new_name}.o"
                unit['metadata']['source_path'] = f"src/{new_name}.c"
        
        with open(objdiff_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        print(f"   ✓ Updated {objdiff_file}")