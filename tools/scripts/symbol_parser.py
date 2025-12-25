"""
Symbol parsing and analysis module
Extracts and organizes symbols from various sources
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from tools.scripts.utils import (
    print_info, print_warning, parse_address, format_address,
    demangle_symbol, ensure_directory
)
from tools.scripts.constants import SYMBOL_FORMATS, TRANSLATION_UNIT_PATTERNS, CODE_BASE_ADDRESS


class Symbol:
    """Represents a function or data symbol"""
    
    def __init__(self, address: int, name: str, size: int = 0, 
                 symbol_type: str = "function", demangled: str = ""):
        self.address = address
        self.name = name
        self.size = size
        self.type = symbol_type
        self.demangled = demangled or demangle_symbol(name)
        self.translation_unit = self._infer_translation_unit()
    
    def _infer_translation_unit(self) -> str:
        """Infer which translation unit this symbol belongs to"""
        for unit_name, pattern in TRANSLATION_UNIT_PATTERNS.items():
            if re.search(pattern, self.name):
                return unit_name
        
        if "::" in self.demangled:
            parts = self.demangled.split("::")
            if len(parts) >= 2:
                return parts[0]
        
        return "Unknown"
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        return {
            "address": format_address(self.address),
            "name": self.name,
            "demangled": self.demangled,
            "size": self.size,
            "type": self.type,
            "translation_unit": self.translation_unit,
        }


class SymbolParser:
    """Parse and organize symbols from various sources"""
    
    def __init__(self, orig_dir: Path, symbols_dir: Path):
        """
        Initialize symbol parser
        
        Args:
            orig_dir: Directory containing extracted ROM files
            symbols_dir: Directory to save symbol files
        """
        self.orig_dir = orig_dir
        self.symbols_dir = symbols_dir
        self.code_bin = orig_dir / "code.bin"
        
        self.symbols: List[Symbol] = []
        self.symbols_by_address: Dict[int, Symbol] = {}
        self.translation_units: Dict[str, List[Symbol]] = defaultdict(list)
    
    def get_symbol_count(self) -> int:
        """Get total number of symbols"""
        return len(self.symbols)
    
    def get_translation_units(self) -> Dict[str, List[Symbol]]:
        """Get symbols organized by translation unit"""
        return dict(self.translation_units)
    
    def load_ida_symbols(self, ida_file: Path):
        """
        Load symbols from IDA Pro export
        
        Expected format:
        ADDRESS TYPE NAME
        00100000 T _start
        00100100 T _ZN4Game4MainEv
        """
        print_info(f"Loading IDA symbols from {ida_file}")
        
        function_pattern = re.compile(SYMBOL_FORMATS["ida"]["function_pattern"])
        data_pattern = re.compile(SYMBOL_FORMATS["ida"]["data_pattern"])
        
        with open(ida_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = function_pattern.match(line)
                if match:
                    addr, sym_type, name = match.groups()
                    symbol = Symbol(
                        address=parse_address(addr),
                        name=name,
                        symbol_type="function"
                    )
                    self._add_symbol(symbol)
                    continue
                
                match = data_pattern.match(line)
                if match:
                    addr, sym_type, name = match.groups()
                    symbol = Symbol(
                        address=parse_address(addr),
                        name=name,
                        symbol_type="data"
                    )
                    self._add_symbol(symbol)
    
    def load_ghidra_symbols(self, ghidra_file: Path):
        """
        Load symbols from Ghidra export
        
        Expected format (CSV):
        Name,Address,Type
        _start,00100000,Function
        Game::Main,00100100,Function
        """
        print_info(f"Loading Ghidra symbols from {ghidra_file}")
        
        with open(ghidra_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            if lines and ('Name' in lines[0] or 'Symbol' in lines[0]):
                lines = lines[1:]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split(',')
                if len(parts) < 3:
                    continue
                
                name = parts[0].strip()
                addr_str = parts[1].strip()
                sym_type = parts[2].strip().lower()
                
                try:
                    addr = parse_address(addr_str)
                except ValueError:
                    logging.warning(f"Invalid address: {addr_str}")
                    continue
                
                symbol = Symbol(
                    address=addr,
                    name=name,
                    symbol_type="function" if "function" in sym_type else "data"
                )
                self._add_symbol(symbol)
    
    def analyze_code_bin(self):
        """
        Perform basic analysis on code.bin to find functions
        This is a simple heuristic-based approach
        """
        if not self.code_bin.exists():
            print_warning("code.bin not found, skipping analysis")
            return
        
        print_info("Analyzing code.bin for function patterns...")
        
        with open(self.code_bin, 'rb') as f:
            data = f.read()
        
        patterns = [
            b'\x2d\xe9',  # PUSH instruction (Thumb-2)
            b'\x00\x48',  # LDR PC relative (Thumb)
            b'\x00\xb5',  # PUSH {lr} (Thumb)
        ]
        
        potential_functions = set()
        
        for pattern in patterns:
            offset = 0
            while True:
                offset = data.find(pattern, offset)
                if offset == -1:
                    break
                
                addr = CODE_BASE_ADDRESS + offset
                
                if offset % 4 == 0 or offset % 2 == 0:
                    potential_functions.add(addr)
                
                offset += 1
        
        print_info(f"Found {len(potential_functions)} potential functions")
        
        for i, addr in enumerate(sorted(potential_functions)):
            symbol = Symbol(
                address=addr,
                name=f"sub_{format_address(addr)}",
                symbol_type="function"
            )
            self._add_symbol(symbol)
        
        self._calculate_symbol_sizes()
    
    def _add_symbol(self, symbol: Symbol):
        """Add a symbol to the collection"""
        if symbol.address in self.symbols_by_address:
            existing = self.symbols_by_address[symbol.address]
            if symbol.name != existing.name and not symbol.name.startswith("sub_"):
                existing.name = symbol.name
                existing.demangled = symbol.demangled
            return
        
        self.symbols.append(symbol)
        self.symbols_by_address[symbol.address] = symbol
        self.translation_units[symbol.translation_unit].append(symbol)
    
    def _calculate_symbol_sizes(self):
        """Calculate symbol sizes based on next symbol address"""
        sorted_symbols = sorted(self.symbols, key=lambda s: s.address)
        
        for i in range(len(sorted_symbols) - 1):
            current = sorted_symbols[i]
            next_sym = sorted_symbols[i + 1]
            
            if current.size == 0:
                current.size = next_sym.address - current.address
    
    def export_symbols(self):
        """Export symbols to various formats"""
        ensure_directory(self.symbols_dir)
        
        self._export_json()
        self._export_symbol_map()
        self._export_translation_units()
        
        print_success(f"✓ Exported symbols to {self.symbols_dir}")
    
    def _export_json(self):
        """Export symbols as JSON"""
        output = {
            "symbols": [s.to_dict() for s in self.symbols],
            "translation_units": {
                name: [s.to_dict() for s in symbols]
                for name, symbols in self.translation_units.items()
            },
            "statistics": {
                "total_symbols": len(self.symbols),
                "functions": len([s for s in self.symbols if s.type == "function"]),
                "data": len([s for s in self.symbols if s.type == "data"]),
                "translation_units": len(self.translation_units),
            }
        }
        
        output_file = self.symbols_dir / "symbols.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
    
    def _export_symbol_map(self):
        """Export symbol map file"""
        output_file = self.symbols_dir / "symbols.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Symbol Map\n")
            f.write("# Format: ADDRESS TYPE NAME [DEMANGLED]\n\n")
            
            for symbol in sorted(self.symbols, key=lambda s: s.address):
                type_char = 'T' if symbol.type == "function" else 'D'
                f.write(f"{format_address(symbol.address)} {type_char} {symbol.name}")
                
                if symbol.demangled != symbol.name:
                    f.write(f" # {symbol.demangled}")
                
                f.write("\n")
    
    def _export_translation_units(self):
        """Export translation units list"""
        output_file = self.symbols_dir / "translation_units.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Translation Units\n\n")
            
            for unit_name in sorted(self.translation_units.keys()):
                symbols = self.translation_units[unit_name]
                f.write(f"{unit_name}:\n")
                f.write(f"  Functions: {len([s for s in symbols if s.type == 'function'])}\n")
                f.write(f"  Data: {len([s for s in symbols if s.type == 'data'])}\n")
                f.write(f"  Total: {len(symbols)}\n\n")
    
    def get_symbol_at_address(self, address: int) -> Optional[Symbol]:
        """Get symbol at specific address"""
        return self.symbols_by_address.get(address)
    
    def get_symbols_as_single_unit_per_symbol(self) -> Dict[str, List['Symbol']]:
        """
        Groups symbols such that each function/data symbol is its own translation unit.
        This uses the symbol name (e.g., 'sub_0010004A') as the unit name.
        """
        single_units = {}
        for symbol in self.symbols:
            if symbol.name:
                unit_name = symbol.name 
                single_units[unit_name] = [symbol]
            
        return single_units
    
    def find_symbols_by_name(self, pattern: str) -> List[Symbol]:
        """Find symbols matching a name pattern"""
        regex = re.compile(pattern)
        return [s for s in self.symbols if regex.search(s.name) or regex.search(s.demangled)]


def print_success(text: str):
    from tools.scripts.utils import Color
    print(f"{Color.OKGREEN}{text}{Color.ENDC}")