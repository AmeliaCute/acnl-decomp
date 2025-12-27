

import argparse
import json
from pathlib import Path

from tools.create_elf import ELFCreator
from tools.extract_rom import ROMExtractor
from tools.ida_map import IDAMap, Symbol


def create_objdiff_config(root_dir: Path, region: str):
    config = {
      "custom_make": "make",
      "target_dir": "build",
      "base_dir": "original",
      "build_target": True,
      "watch_patterns": [
          "*.c",
          "*.cpp",
          "*.h",
          "*.hpp",
          "Makefile"
      ],
      "units": [
          {
              "name": "game",
              "target_path": f"origin/{region}/code.elf",
              "base_path": "build/game.elf"
          }
      ]
    }
    
    config_file = root_dir / "objdiff.json"
    with open(str(config_file), 'w') as f:
        json.dump(config, f, indent=2)
        
    print(f"✓ ObjDiff config created at: {config_file}")
  
    
def create_linker_script(linker_path: Path, base_addr: int, symbols: list[Symbol]):
    text_symbols = [s for s in symbols if s.type in ["function", "object"]]
    
    symbol_placements = []
    for sym in text_symbols:
        offset = sym.address - base_addr
        symbol_placements.append(f"    . = 0x{offset:X}; KEEP(*(.text.{sym.name}))")
    
    linker_content = f"""/* ACNL Linker Script - Auto-generated symbol placement */

OUTPUT_FORMAT("elf32-littlearm", "elf32-bigarm", "elf32-littlearm")
OUTPUT_ARCH(arm)

ENTRY(start)

MEMORY
{{
    rom : ORIGIN = 0x{base_addr:08X}, LENGTH = 16M
}}

SECTIONS
{{
    .text 0x{base_addr:08X} : ALIGN(4) {{
{chr(10).join(symbol_placements)}
        
        /* Catch-all for remaining functions */
        *(.text)
        *(.text.*)
        *(.glue_7)
        *(.glue_7t)
        
        . = ALIGN(4);
    }} > rom

    .rodata : ALIGN(4) {{
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(4);
    }} > rom

    .data : ALIGN(4) {{
        *(.data)
        *(.data.*)
        . = ALIGN(4);
    }} > rom

    .bss : ALIGN(4) {{
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
    }} > rom

    /DISCARD/ : {{
        *(.ARM.exidx*)
        *(.ARM.extab*)
        *(.ARM.attributes)
        *(.note.*)
        *(.comment)
        *(.eh_frame*)
    }}
}}
"""
    
    with open(linker_path, 'w') as f:
        f.write(linker_content)
    
    print(f"✓ Linker script created with {len(symbol_placements)} symbol placements")
  
    
def create_makefile(root_dir: Path, region: str, symbols: list[Symbol]):
    base_addr = symbols[0].address if symbols else 0x00100000
    
    linker_script = root_dir / "linker.ld"
    create_linker_script(linker_script, base_addr, symbols)
    
    makefile_content = f"""# ACNL Decompilation Makefile
# Region: {region}

TARGET := game
BUILD := build
SOURCES := src
INCLUDES := include
DATA := data

BASEADDR := 0x{base_addr:08X}

ARCH := -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft

# Compiler flags avec sections par fonction
CFLAGS := -g -O2 -mword-relocations \\
          -ffunction-sections -fdata-sections \\
          -fno-strict-aliasing -fno-builtin \\
          $(ARCH) $(INCLUDE)

CXXFLAGS := $(CFLAGS) -fno-rtti -fno-exceptions -std=gnu++11

# Linker flags
LDFLAGS := -nostartfiles -nodefaultlibs -nostdlib \\
           $(ARCH) \\
           -Wl,-Map,$(BUILD)/$(TARGET).map \\
           -Wl,--no-warn-rwx-segments \\
           -Wl,-T,linker.ld

ASFLAGS := $(ARCH) -g

PREFIX := arm-none-eabi-
CC := $(PREFIX)gcc
CXX := $(PREFIX)g++
AS := $(PREFIX)as
LD := $(CC)
OBJCOPY := $(PREFIX)objcopy
NM := $(PREFIX)nm
OBJDUMP := $(PREFIX)objdump

CFILES := $(foreach dir,$(SOURCES),$(wildcard $(dir)/*.c))
CPPFILES := $(foreach dir,$(SOURCES),$(wildcard $(dir)/*.cpp))
SFILES := $(foreach dir,$(SOURCES),$(wildcard $(dir)/*.s))

OFILES := $(CFILES:%.c=$(BUILD)/%.o) \\
          $(CPPFILES:%.cpp=$(BUILD)/%.o) \\
          $(SFILES:%.s=$(BUILD)/%.o)
          
INCLUDE := $(foreach dir,$(INCLUDES),-I$(dir))

.PHONY: all clean symbols disasm verify

all: $(BUILD)/$(TARGET).elf
\t@$(MAKE) --no-print-directory verify

$(BUILD)/$(TARGET).elf: $(OFILES)
\t@echo "Linking $@..."
\t@mkdir -p $(dir $@)
\t@$(LD) $(LDFLAGS) $^ -o $@
\t@echo "Built: $@"

$(BUILD)/%.o: %.c
\t@echo "Compiling $<..."
\t@mkdir -p $(dir $@)
\t@$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%.o: %.cpp
\t@echo "Compiling $<..."
\t@mkdir -p $(dir $@)
\t@$(CXX) $(CXXFLAGS) -c $< -o $@

$(BUILD)/%.o: %.s
\t@echo "Assembling $<..."
\t@mkdir -p $(dir $@)
\t@$(AS) $(ASFLAGS) $< -o $@

verify: $(BUILD)/$(TARGET).elf
\t@echo ""
\t@echo "=== Build Verification ==="
\t@echo -n "Symbols: "
\t@$(NM) $< | wc -l
\t@echo -n "Code size: "
\t@$(PREFIX)size $< | tail -1 | awk '{{print $$1 " bytes"}}'
\t@echo ""
\t@echo "First 10 symbols:"
\t@$(NM) -n $< | head -10

symbols: $(BUILD)/$(TARGET).elf
\t@$(NM) -n $<

disasm: $(BUILD)/$(TARGET).elf
\t@$(OBJDUMP) -d $< | less

clean:
\t@echo "Cleaning..."
\t@rm -rf $(BUILD)
"""

    makefile = root_dir / "Makefile"
    with open(str(makefile), 'w') as f:
        f.write(makefile_content)
        
    print(f"✓ Makefile created at: {makefile}")
    
    
def main():
    parser = argparse.ArgumentParser(description="Configure ACNL decompilation project", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", type=str, default="EGDP", help="Game region (default: EGDP)")
    
    args = parser.parse_args()
    root_dir = Path(".")
  
    rom = ROMExtractor(root_dir, args.region)
    rom.extract()
    
    parser = IDAMap(root_dir, args.region)
    symbols = parser.parse()
    
    for sym in symbols[:10]:
        print(f"  {sym}")
    
    output = root_dir / "origin" / args.region / "gnu_symbols.txt"
    parser.export_symbols_txt(output)
    print(f"Symbols exported at: {output}")
    
    elf = ELFCreator(root_dir, args.region, symbols)
    elf.create_elf_with_symbols()
    
    create_objdiff_config(root_dir, args.region)
    create_makefile(root_dir, args.region, symbols)
    
    
if __name__ == "__main__":
    main()