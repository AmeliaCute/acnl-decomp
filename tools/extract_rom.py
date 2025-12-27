

from pathlib import Path
import subprocess
from typing import Optional
from tools.utils import find_tool


class ROMExtractor:
    def __init__(self, root_dir: Path, region: str):
        self.origin_dir = root_dir / "origin" / region
        self.rom_path = self.find_rom_file()
      
    def extract(self):
        content_file = self.extract_content()
        if not content_file:
            return None
        
        exefs_file = self.extract_cxi(content_file)
        if not exefs_file:
            return None
        
        code_file = self.extract_exefs(exefs_file)
        if not code_file:
            return None
        
        print(f"\n✓ Extraction finished: {code_file}")
      
    def find_rom_file(self) -> Optional[Path]:
        """Find the ROM file to extract"""
        for pattern in ["*.3ds", "*.cia", "*.cxi"]:
            files = list(self.origin_dir.glob(pattern))
            if files:
                return files[0]
        return None
      
    def extract_content(self):
        print("Extracting contents")
        
        ctrtool = find_tool("ctrtool")
        if not ctrtool.exists():
            print("Ctrtool is missing!")
            return None
        
        contents_path = self.origin_dir / "contents"
        contents_path.mkdir(exist_ok=True)
        
        cmd = [
            str(ctrtool), 
            f"--contents={contents_path}", 
            str(self.rom_path)
        ]
        
        result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Ctrtool error: {result.stderr}")

        content_files = list(contents_path.glob("*.app"))
        if not content_files:
            print(f"Error {contents_path} is empty")
            return None
        
        return content_files[0]
    
    def extract_cxi(self, content_file):
        print("Extracting CXI")
        
        dstool = find_tool("3dstool")
        if not dstool.exists():
            print("3dstool is missing!")
            return None
        
        contents_path = self.origin_dir / "cxi"
        contents_path.mkdir(exist_ok=True)
        
        cmd = [
            str(dstool),
            "-xvtf", "cxi",
            str(content_file),
            '--header', str(contents_path / 'ncchheader.bin'),
            '--exh', str(contents_path / 'exheader.bin'),
            '--logo', str(contents_path / 'logo.bin'),
            '--plain', str(contents_path / 'plain.bin'),
            '--exefs', str(contents_path / 'exefs.bin'),
            '--romfs', str(contents_path / 'romfs.bin')
        ]
        
        result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"3dstool error: {result.stderr}")
            
        return contents_path / "exefs.bin"
    
    def extract_exefs(self, content_file):
        print("Extracting Exefs")
        
        dstool = find_tool("3dstool")
        if not dstool.exists():
            print("3dstool is missing!")
            return None
        
        contents_path = self.origin_dir / "exefs"
        contents_path.mkdir(exist_ok=True)
        
        cmd = [
            str(dstool),
            '-xvtf', 'exefs',
            str(content_file),
            '--exefs-dir', str(contents_path)
        ]
        
        result = subprocess.run(cmd, cwd=Path("."), capture_output=True, text=True)
        if result.returncode != 0:
            print(f"3dstool error: {result.stderr}")
            
        code_file = contents_path / 'code.bin'
        if not code_file.exists():
            print(f"{code_file} not found.")
            return None
            
        return code_file
