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
        
        print(f"Setting .text VMA to 0x{self.base_address:08X}...")
        cmd = [
          'arm-none-eabi-objcopy',
          '--change-section-vma', f'.text=0x{self.base_address:08X}',
          '--change-section-lma', f'.text=0x{self.base_address:08X}',
          str(self.code_elf),
          str(self.code_elf)
        ]
        
        result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"arm-none-eabi-objcopy error: {result.stderr}")
        
        result = subprocess.run(
            ['arm-none-eabi-readelf', '-S', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        if '00100000' in result.stdout:
            print("✓ Base ELF created with correct VMA")
        else:
            print("WARNING: VMA might not be set correctly")
        
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
        
        self.verify_elf()
        return True
          
    def verify_elf(self):
        print("\nELF Verification:")
        
        result = subprocess.run(
            ['arm-none-eabi-readelf', '-S', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("\n  Sections:")
            for line in result.stdout.split('\n'):
                if '.text' in line or 'Name' in line or 'Addr' in line:
                    print(f"    {line.strip()}")
        
        result = subprocess.run(
            ['arm-none-eabi-nm', '-n', str(self.code_elf)],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            symbols_list = [s for s in result.stdout.split('\n') if s.strip() and not s.startswith('00000000')]
            print(f"\n  Total symbols: {len(symbols_list)}")
            print("\n  First 5 symbols (should start at 0x00100000):")
            for line in symbols_list[:5]:
                if line.strip():
                    print(f"    {line}")