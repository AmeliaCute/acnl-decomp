
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tools.scripts.exheader_parser import ExHeaderParser, IDAConfigGenerator


REQUIRED_TOOLS = [
  "3dstool", 
  "ctrtool"
]


class ROMExtractor:
    def __init__(self, version: str):
        self.version = version
        self.config_path = Path("origin") / "title.json"
        
        self.tools_dir = Path("tools")
        self.origin_dir = Path("origin") / self.version
        self.rom_path = self._resolve_rom()
        
        self.work_dir = Path("build/extract")
        self.config = self._load_configs()

    def _resolve_rom(self):
        roms = list(self.origin_dir.glob("*.3ds"))
        
        if not roms:
            print("[ROM extraction] No .3ds files found in the folder.")
            sys.exit(1)
            
        return roms[0]
  
    def _load_configs(self) -> dict:
        try:
            with open(self.config_path, 'r') as f:
                content = f.read()
                data = json.loads(content)

                if "valide_titles" not in data:
                    raise ValueError("missing 'valide_titles' in config")

                return data["valide_titles"]

        except Exception as error:
            print(f"[ROM extraction] failed to load config: {error}")
            sys.exit(1)
        
    def _validate_version(self) -> bool:
        if self.version not in self.config:
            print(f"[ROM extraction] unknown version: {self.version}")
            print(f"[ROM Extraction] valid versions: {', '.join(self.config.keys())}")
            return False
        return True
    
    def _check_tools(self):
        missing = []
        is_windows = sys.platform.startswith("win")

        for tool in REQUIRED_TOOLS:
            tool_path = self.tools_dir / tool

            possible_paths = [tool_path]

            if is_windows:
                possible_paths.append(tool_path.with_suffix(".exe"))

            found = any(p.exists() for p in possible_paths) or shutil.which(tool)

            if not found:
                missing.append(tool)

        if missing:
            print(f"[ROM extraction] missing tools: {', '.join(missing)}")
            return False

        return True
    
    def _get_tool_path(self, tool: str) -> str:
        is_windows = sys.platform.startswith("win")

        if is_windows:
            exe_path = self.tools_dir / f"{tool}.exe"
            if exe_path.exists():
                return str(exe_path)

        local_path = self.tools_dir / tool
        if local_path.exists():
            return str(local_path)

        return tool
    
    def _calculate_sha256(self) -> str:
        sha256_hash = hashlib.sha256()
        with open(self.rom_path, "rb") as f:
            for byte_block in iter(lambda: f.read(8192), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def _verify_rom(self) -> bool:
        print(f"[ROM extraction] verifying 3DS files for {self.version}")

        with open(self.rom_path, 'rb') as f:
            f.seek(0x100)
            magic = f.read(4)
            if magic != b'NCSD':
                print("[ROM extraction] invalid 3DS format - missing NCSD magic")
                sys.exit(1)

        expected = self.config[self.version]
      
        print("[ROM extraction] calculating SHA256 hash")
        sha256 = self._calculate_sha256()
        print(f"[ROM extraction] SHA256: {sha256}")
        
        if sha256 != expected['sha256']:
            print("[ROM extraction] hash mismatch!")
            print(f"[ROM extraction] expected: {expected['sha256']}")
            print(f"[ROM extraction] got:      {sha256}")
            print(f"[ROM extraction] this may not be the correct {self.version}!")
            return False
        
        print(f"[ROM extraction] region: {expected['region']}")
        return True
    
    def _extract_3ds(self) -> bool:
        print("[ROM extraction] (1/2) extracting NCSD partitions")

        self.work_dir.mkdir(parents=True, exist_ok=True)

        out0 = self.work_dir / "0.cxi"
        out1 = self.work_dir / "1.cfa"
        out7 = self.work_dir / "7.cfa"
        ncsd_header = self.work_dir / "ncsdheader.bin"

        command = [
            self._get_tool_path("3dstool"),
            "-xvt017f", "cci",
            str(out0),
            str(out1),
            str(out7),
            str(self.rom_path),
            "--header", str(ncsd_header)
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ROM extraction] 3DS extraction failed: {result.stderr}")
            return False

        if not out0.exists():
            print("[ROM extraction] 0.cxi not found")
            return False

        print("[ROM extraction] partitions extracted")

        self.extracted_cxi = out0
        return True
    
    def _extract_cxi(self) -> bool:
        print("[ROM extraction] (2/2) extracting ExeFS & RomFS")

        cxi_path = self.extracted_cxi
        exefs_dir = self.work_dir / "exefs"
        romfs_dir = self.work_dir / "romfs"
        exheader_file = self.work_dir / "exefs" / "exheader.bin"

        exefs_dir.mkdir(exist_ok=True)
        romfs_dir.mkdir(exist_ok=True)
        
        print("[ROM extraction] extracting ExHeader")
        exheader_command = [
            self._get_tool_path("ctrtool"),
            "-t", "ncch",
            "--exheader=" + str(exheader_file),
            str(cxi_path)
        ]
        
        result = subprocess.run(exheader_command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ROM extraction] warning: ExHeader extraction failed: {result.stderr}")
            print("[ROM extraction] continuing anyway")
        else:
            if exheader_file.exists():
                size = exheader_file.stat().st_size
                print(f"[ROM extraction] ExHeader extracted ({size} bytes)")
            else:
                print("[ROM extraction] ExHeader file not created")

        print("[ROM extraction] extracting ExeFS & RomFS")
        command = [
            self._get_tool_path("ctrtool"),
            "-t", "ncch",
            "--exefsdir=" + str(exefs_dir),
            "--romfsdir=" + str(romfs_dir),
            str(cxi_path)
        ]

        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ROM extraction] CXI extraction failed: {result.stderr}")
            return False

        print("[ROM extraction] exeFS & RomFS extracted")
        return True
      
    def _copy_code_bin(self) -> bool:
        print("[ROM extraction] copying code.bin")
        
        code_bin = self.work_dir / "exefs" / "code.bin"
        if not code_bin.exists():
            code_bin = self.work_dir / "exefs" / ".code"
        
        if not code_bin.exists():
            print("[ROM extraction] code.bin not found in extraction")
            print("[ROM extraction] ExeFS contents:")
            exefs_dir = self.work_dir / "exefs"
            if exefs_dir.exists():
                for f in exefs_dir.iterdir():
                    print(f"     - {f.name} ({f.stat().st_size} bytes)")
            return False
        
        self.origin_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.origin_dir / "code.bin"
        shutil.copy2(code_bin, output_path)
        
        size_kb = code_bin.stat().st_size / 1024
        print(f"[ROM extraction] saved to: {output_path}")
        print(f"[ROM extraction] size: {size_kb:.2f} KB")
        
        return True
    
    def _cleanup(self):
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)
            print("[ROM extraction] cleaned up temporary files")
            
    def extract(self) -> bool:
        print("[ROM extraction] Animal Crossing: New Leaf - ROM Extractor")
        print(f"[ROM extraction] version: {self.version}")
        
        if not self._validate_version():
            return False
        
        if not self._check_tools():
            return False
        
        if not self._verify_rom():
            return False
        
        if not self._extract_3ds():
            return False
        
        if not self._extract_cxi():
            return False
        
        exefs_dir = self.work_dir / "exefs"
        parser = ExHeaderParser(exefs_dir)
        exheader_info = parser.parse()
        parser.print_info(exheader_info)
        
        if not self._copy_code_bin():
            return False

        ida_config_path = self.origin_dir / "ida_config.md"
        IDAConfigGenerator.generate(exheader_info, self.version, ida_config_path)
        
        # self._cleanup()
        return True