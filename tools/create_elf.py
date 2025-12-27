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
        
    def create_base_elf(self):
        print("Creating ELF base")
        
        cmd = [
          'arm-none-eabi-objcopy',
          '-I', 'binary',
          '-O', 'elf32-littlearm',
          '-B', 'arm',
          '--rename-section', '.data=.text',
          '--set-section-flags', '.text=alloc,code,readonly,contents',
          '--change-section-address', f'.text=0x{self.base_address:08X}',
          str(self.code_bin),
          str(self.code_elf)
        ]
        
        result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"arm-none-eabi-objcopy error: {result.stderr}")
            
        print(f"✓ ELF files created at: {self.code_elf}")
        return True
      
    def add_symbols(self):
        print("Adding symbols")
        temp_elf = self.code_elf.with_suffix('.tmp')
        shutil.copy(self.code_elf, temp_elf)
        
        batch_size = 250
        for i in range(0, len(self.symbols), batch_size):
            batch = self.symbols[i:i+batch_size]

            cmd = ['arm-none-eabi-objcopy']
            for object in batch:
                offset = object.address - self.base_address
              
                cmd.extend([
                  '--add-symbol',
                  f'{object.name}=.text:0x{offset:X},{object.type},global'
                ])
                
            cmd.extend([str(temp_elf), str(temp_elf)])
            result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
            if result.returncode != 0:
                print(f"arm-none-eabi-objcopy error: {result.stderr}")
                
            if i % 500 == 0 and i > 0:
                print(f"\r{i}/{len(self.symbols)} symbols injected", end="", flush=True)

        shutil.move(temp_elf, self.code_elf)
        print("\n✓ All symboles addded")
        
        return True
      
    def create_elf_with_symbols(self):
        if not self.create_base_elf():
            return False
          
        if not self.add_symbols():
            return False
          
        print(f"\n✓ full ELF with symboles created at: {self.code_elf}")
        return True
          