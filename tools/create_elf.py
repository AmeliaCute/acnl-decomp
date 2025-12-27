from pathlib import Path
import shutil
import subprocess

from tools.ida_map import Symbol


class ELFCreator:
    def __init__(self, root_dir: Path, region: str, symbols: list[Symbol], base_address=0x00100000):
        origin_dir = root_dir / "origin" / region
        self.code_bin = origin_dir / "exefs" / "code.bin"
        self.code_elf = origin_dir / "code.elf"
        self.symbols = symbols
        self.base_address = base_address
        self.text_size = self.code_bin.stat().st_size
        
    def create_base_elf(self):
        print("Creating executable ELF from code.bin")
        
        temp_obj = self.code_elf.with_suffix('.tmp.o')
        
        cmd = [
            'arm-none-eabi-objcopy',
            '-I', 'binary',
            '-O', 'elf32-littlearm',
            '-B', 'arm',
            '--rename-section', '.data=.text',
            '--set-section-flags', '.text=code,alloc,load,readonly,contents',
            str(self.code_bin),
            str(temp_obj)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"arm-none-eabi-objcopy error: {result.stderr}")
            return False
        
        linker_script = self.code_elf.with_suffix('.ld')
        with open(linker_script, 'w') as f:
            f.write(f"""
OUTPUT_FORMAT("elf32-littlearm")
OUTPUT_ARCH(arm)
/* no ENTRY */

PHDRS
{{
    text PT_LOAD FLAGS(5); /* Read + Execute */
}}

SECTIONS
{{
    . = 0x{self.base_address:08X};
    
    .text : ALIGN(4) {{
        *(.text)
        *(.text.*)
        . = ALIGN(4);
    }} :text
    
    /DISCARD/ : {{
        *(.ARM.exidx*)
        *(.ARM.extab*)
        *(.note.*)
        *(.comment)
        *(.eh_frame*)
    }}
}}
""")
        
        cmd = [
            'arm-none-eabi-ld',
            '-T', str(linker_script),
            '--oformat=elf32-littlearm',
            '-o', str(self.code_elf),
            str(temp_obj)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"arm-none-eabi-ld error: {result.stderr}")
            temp_obj.unlink(missing_ok=True)
            linker_script.unlink(missing_ok=True)
            return False
        
        temp_obj.unlink(missing_ok=True)
        linker_script.unlink(missing_ok=True)
        
        result = subprocess.run(['arm-none-eabi-readelf', '-h', str(self.code_elf)], capture_output=True, text=True) 
        
        if 'EXEC' in result.stdout:
            print("✓ Executable ELF created successfully")
        else:
            print("WARNING: ELF type might not be EXEC")
            
        result = subprocess.run(
            ['arm-none-eabi-readelf', '-l', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        if 'LOAD' in result.stdout:
            print("✓ Program headers present")
        else:
            print("WARNING: No program headers found")
        
        return True
      
    def add_symbols(self):
        print("\nAdding symbols to ELF...")
        
        valid_symbols = []
        invalid_count = 0
        
        for sym in self.symbols:
            offset = sym.address - self.base_address
            if 0 <= offset < self.text_size:
                valid_symbols.append(sym)
            else:
                invalid_count += 1
        
        if invalid_count > 0:
            print(f"Skipped {invalid_count} out-of-bounds symbols")
        
        print(f"Adding {len(valid_symbols)} valid symbols...")
        
        temp_elf = self.code_elf.with_suffix('.tmp')
        shutil.copy(self.code_elf, temp_elf)
        
        batch_size = 200
        for i in range(0, len(valid_symbols), batch_size):
            batch = valid_symbols[i:i+batch_size]

            cmd = ['arm-none-eabi-objcopy']
            for symbol in batch:
                offset = (symbol.address - self.base_address) | 1
              
                cmd.extend([
                    '--add-symbol',
                    f'{symbol.name}=.text:0x{offset:X},{symbol.type},global'
                ])
                
            cmd.extend([str(temp_elf), str(temp_elf)])
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"arm-none-eabi-objcopy error: {result.stderr}")
                temp_elf.unlink(missing_ok=True)
                return False
                
            if (i + batch_size) % 1000 == 0:
                print(f"▢ Progress: {i + batch_size}/{len(valid_symbols)} symbols", end='\r', flush=True)

        shutil.move(temp_elf, self.code_elf)
        print(f"\n✓ {len(valid_symbols)} symbols added successfully")
        
        return True
      
    def create_elf_with_symbols(self):
        print("="*32)
        print("Creating ELF with symbols")
        print("="*32)
        print(f"Input:  {self.code_bin}")
        print(f"Output: {self.code_elf}")
        print(f"Size:   0x{self.text_size:X} bytes")
        print(f"Base:   0x{self.base_address:08X}")
        print()
        
        if not self.create_base_elf():
            return False
          
        if not self.add_symbols():
            return False
          
        print(f"\n✓ Full ELF with symbols created at: {self.code_elf}")
        
        self.verify_elf()
        return True
          
    def verify_elf(self):
        print("\n" + "="*32)
        print("ELF Verification")
        print("="*32)
        
        result = subprocess.run(
            ['arm-none-eabi-readelf', '-h', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        print("\nELF Header:")
        for line in result.stdout.split('\n'):
            if 'Type:' in line or 'Entry point' in line or 'Machine:' in line:
                print(f"  {line.strip()}")
        
        result = subprocess.run(
            ['arm-none-eabi-readelf', '-S', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        print("\nSections:")
        for line in result.stdout.split('\n'):
            if '.text' in line or 'Name' in line:
                print(f"  {line.strip()}")
        
        result = subprocess.run(['arm-none-eabi-readelf', '-l', str(self.code_elf)], capture_output=True, text=True)
        
        has_headers = 'LOAD' in result.stdout
        print(f"\nProgram Headers: {'✓ Present' if has_headers else 'Missing'}")
        
        result = subprocess.run(['arm-none-eabi-nm', str(self.code_elf)], capture_output=True, text=True)
        
        symbol_count = len([l for l in result.stdout.split('\n') if l.strip()])
        print(f"Total Symbols: {symbol_count}")
        
        result = subprocess.run(
            ['arm-none-eabi-nm', '-n', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        symbols_list = [s for s in result.stdout.split('\n') if s.strip()]
        print("\nFirst 5 symbols:")
        for line in symbols_list[:5]:
            if line.strip():
                print(f"  {line}")
        
        print("\n" + "="*50)