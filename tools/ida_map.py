from dataclasses import dataclass
from pathlib import Path
import re

from tools.utils import parse_hex


@dataclass 
class Symbol:
    address: int
    name: str
    section: str = ""
    type: str = "function"
    
    def __str__(self):
        return f"0x{self.address:08X} {self.type:8s} {self.name}"
      
      
class IDAMap:
    def __init__(self, root_dir: Path, region: str):
        self.map_file = root_dir / "origin" / region / "code.bin.map"
        self.base_address = 0
        self.sections = {}
        self.symbols = []
    
    def parse(self) -> list[Symbol]: 
        with open(self.map_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        self.parse_sections(lines)
        self.parse_symbols(lines)
        
        return self.symbols
      
    def parse_sections(self, lines):
        in_sections = False
        
        for line in lines:
            if 'Start' in line and 'Length' in line and 'Name' in line:
                in_sections = True
                continue
              
            if in_sections:
                # Format: " 0000:00000000 000XXXXXXX .text                  CODE"
                match = re.match(r'\s*\w+:(\w+)\s+(\w+)H?\s+(\S+)\s+(\S+)', line)
                if match:
                    offset = int(parse_hex(match.group(1)))
                    length = int(parse_hex(match.group(2)))
                    name = match.group(3)
                    section_type = match.group(4)
                    
                    self.sections[name] = {
                        'offset': offset,
                        'length': length,
                        'type': section_type
                    }
                        
            elif line.strip() == '':
                in_sections = False
                
    def parse_symbols(self, lines):
        in_symbols = False

        for line in lines:
            if 'Publics by Value' in line or 'Address' in line and 'Publics' in line:
                in_symbols = True
                continue
              
            if in_symbols and line.strip():
                # Format: " 0000:00XXXXXX       start"
                match = re.match(r'\s*\w+:(\w+)\s+(\S+)', line)
                if match:
                    addr_hex = match.group(1)
                    name = match.group(2)
                    
                    try:
                        address = parse_hex(addr_hex)
                    except ValueError:
                        continue
                      
                    symbol_type = "function"
                    if name.startswith("a") or any(name.startswith(prefix) for prefix in ["byte_", "dbl_", "def_", "flt_", "word_", "dword_", "qword_", "unk_", "off_", "stru_", "typeinfo for", "vtable for"]):
                        symbol_type = "object"
                    elif any(name.startswith(prefix) for prefix in ["loc_", "locret_", "jpt_"]):
                        continue
                        
                    symbol = Symbol(address=address, name=name, type=symbol_type)
                    
                    self.symbols.append(symbol)
                    
        self.symbols.sort(key=lambda s: s.address)
        if self.base_address == 0:
            self.base_address = self.symbols[0].address
            
        print(f"✓ {len(self.symbols)} symbols found!")
        print(f"✓ Base address: 0x{self.base_address:08X}")
        
    def export_symbols_txt(self, output_file):
        with open(output_file, 'w') as f:
            for sym in self.symbols:
                f.write(f"{sym.name} 0x{sym.address:08X}\n")
    
    def export_symbols_map(self, output_file):
        with open(output_file, 'w') as f:
            f.write(f"# Generated from {self.map_file.name}\n")
            f.write(f"# Base address: 0x{self.base_address:08X}\n\n")
            
            for sym in self.symbols:
                f.write(f"0x{sym.address:08X} {sym.name}\n")