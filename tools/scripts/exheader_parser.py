import struct
from pathlib import Path
from typing import Dict


class ExHeaderParser:
    PAGE_SIZE = 0x1000
    
    def __init__(self, exefs_dir: Path):
        self.exefs_dir = exefs_dir
        self.exheader_path = exefs_dir / "exheader.bin"
    
    def parse(self) -> Dict[str, int]:
        if not self.exheader_path or not self.exheader_path.exists():
            print("[ExHeader] warning ExHeader not found, using defaults")
            return self._get_default_info()
        
        try:
            with open(self.exheader_path, 'rb') as f:
                exheader_data = f.read()
                size = len(exheader_data)
                
                if size < 0x30:
                    print(f"[ExHeader] error ExHeader too small ({size} bytes)")
                    return self._get_default_info()
                
                f.seek(0x00)
                app_title_bytes = f.read(8)
                app_title = app_title_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                
                f.seek(0x10)
                load_address = struct.unpack('<I', f.read(4))[0]
                code_size_pages = struct.unpack('<I', f.read(4))[0]
                code_size_bytes = code_size_pages * self.PAGE_SIZE
                
                entry_offset = struct.unpack('<I', f.read(4))[0]
                stack_size = struct.unpack('<I', f.read(4))[0]
                entry_point = load_address + entry_offset
                
                print(f"[ExHeader] code size: {code_size_pages} pages * 4KB = {code_size_bytes / 1024:.2f} KB")
                info = {
                    'load_address': load_address,
                    'code_size': code_size_bytes,
                    'entry_point': entry_point,
                    'entry_offset': entry_offset,
                    'stack_size': stack_size,
                    'app_title': app_title
                }
                
                if code_size_bytes < 0x10000 or code_size_bytes > 0x2000000:
                    print(f"[ExHeader] warning code size seems unusual: {code_size_bytes / 1024:.2f} KB")
                
                return info
                
        except Exception as e:
            print(f"[ExHeader] error parsing ExHeader: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_info()
    
    def _get_default_info(self) -> Dict[str, int]:
        return {
            'load_address': 0x00100000,
            'code_size': 0x00900000,
            'entry_point': 0x00100000,
            'entry_offset': 0x00000000,
            'stack_size': 0x00080000,
            'app_title': 'Unknown'
        }
    
    def print_info(self, info: Dict[str, int]) -> None:
        print(f"[ExHeader] application:     {info.get('app_title', 'Unknown')}")
        print(f"[ExHeader] load Address:    0x{info['load_address']:08X}")
        print(f"[ExHeader] code Size:       0x{info['code_size']:08X} ({info['code_size'] / 1024:.2f} KB)")
        print(f"[ExHeader] entry Point:     0x{info['entry_point']:08X}")
        print(f"[ExHeader] entry Offset:    0x{info['entry_offset']:08X}")
        print(f"[ExHeader] stack Size:      0x{info['stack_size']:08X} ({info['stack_size'] / 1024:.2f} KB)")


class IDAConfigGenerator:
    @staticmethod
    def generate(info: Dict[str, int], version: str, output_path: Path) -> bool:
        app_title = info.get('app_title', 'Unknown')
        
        config_text = f"""# Animal Crossing: New Leaf - Reverse Engineering Configuration
**Game Version:** `{version}`  
**Application Title:** `{app_title}`  
**Extracted:** {Path(output_path).parent / 'code.bin'}

## 🔧 IDA Pro Setup

### Step 1: Load File
- **File -> Open** -> Select `code.bin`

### Step 2: Processor Configuration
- **Processor type:** `ARM Little-endian [ARM]`
- **Bitness:** `32-bit`
- **Do NOT select ARM64/AArch64** (3DS is 32-bit ARM11)

### Step 3: Loading Options
| Setting | Value |
|---------|-------|
| File type | Binary file |
| Loading address | `0x{info['load_address']:08X}` |
| Loading offset | `0x00000000` |

### Step 4: Post-Load Configuration

1. **Navigate to Entry Point:**
  - Press `G` (Go to address)
  - Enter: `0x{info['entry_point']:08X}`
  - Press `C` to convert to code

2. **Set ARM Mode:**
  - Press `Alt+G` (Edit Segment)
  - Set `T` register = `0` (ARM mode, not Thumb)
  - If code looks wrong, try `T = 1`

3. **Start Analysis:**
  - Wait for IDA auto-analysis to complete
  - Look for function names in the Functions window
  - Press `F5` on any function to decompile

## 📊 Technical Information

| Property | Value | Notes |
|----------|-------|-------|
| **Load Address** | `0x{info['load_address']:08X}` | Where code loads in 3DS memory |
| **Code Size** | `0x{info['code_size']:08X}` | {info['code_size'] / 1024:.2f} KB ({info['code_size'] / 1024 / 1024:.2f} MB) |
| **Entry Point** | `0x{info['entry_point']:08X}` | First instruction executed |
| **Entry Offset** | `0x{info['entry_offset']:08X}` | Offset from base address |
| **Stack Size** | `0x{info['stack_size']:08X}` | {info['stack_size'] / 1024:.2f} KB |

## 💡 Tips

- **Finding functions:** Look for function prologues (`push {{...}}, lr`)
- **Strings:** Search for readable strings to find interesting code
- **Cross-references:** Use `X` in IDA to see where functions are called
- **Save your work:** IDA creates `.idb` files, Ghidra uses projects

## 🔍 3DS Specifics

- **Processor:** ARM11 (ARMv6K architecture)
- **Endianness:** Little-endian
- **Thumb mode:** 3DS can use both ARM and Thumb instructions
- **System calls:** Look for `svc` instructions (supervisor calls)
        """
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(config_text)
            
            print(f"[IDA Config] configuration saved to: {output_path}")
            return True
            
        except Exception as e:
            print(f"[IDA Config] failed to save configuration: {e}")
            return False


def parse_exheader(exefs_dir: Path) -> Dict[str, int]:
    parser = ExHeaderParser(exefs_dir)
    return parser.parse()