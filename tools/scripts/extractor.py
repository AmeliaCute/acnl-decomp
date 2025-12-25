"""
ROM extraction module for 3DS games
Handles .3ds, .cia, and .cxi file extraction
"""

import logging
from pathlib import Path
from typing import Optional
import shutil

from tools.scripts.utils import run_command, find_tool, print_info, print_success, ensure_directory
from tools.scripts.constants import ROM_EXTENSIONS


class ROMExtractor:
    """Handle 3DS ROM extraction"""
    
    def __init__(self, tools_dir: Path, origin_dir: Path, output_dir: Path):
        """
        Initialize ROM extractor
        
        Args:
            tools_dir: Directory containing extraction tools
            origin_dir: Directory containing ROM files
            output_dir: Directory to extract files to
        """
        self.tools_dir = tools_dir
        self.origin_dir = origin_dir
        self.output_dir = output_dir
        
        # Find required tools
        self.ctrtool = find_tool(tools_dir, "ctrtool")
        self.dstool = find_tool(tools_dir, "3dstool")
        
        # Extraction paths
        self.temp_dir = output_dir / "temp"
        self.exefs_dir = self.temp_dir / "exefs"
        self.romfs_dir = self.temp_dir / "romfs"
        
    def verify_rom_exists(self) -> bool:
        """Check if a ROM file exists in the origin directory"""
        if not self.origin_dir.exists():
            return False
        
        for ext in ROM_EXTENSIONS:
            if list(self.origin_dir.glob(f"*{ext}")):
                return True
        return False
    
    def find_rom_file(self) -> Optional[Path]:
        """Find the ROM file to extract"""
        for ext in ROM_EXTENSIONS:
            files = list(self.origin_dir.glob(f"*{ext}"))
            if files:
                return files[0]  # Return first match
        return None
    
    def extract(self, force: bool = False):
        """
        Extract ROM file
        
        Args:
            force: Force re-extraction even if files exist
        """
        # Check if already extracted
        code_bin = self.output_dir / "code.bin"
        if code_bin.exists() and not force:
            print_info("code.bin already exists, skipping extraction")
            print_info("Use --force to re-extract")
            return
        
        # Find ROM file
        rom_file = self.find_rom_file()
        if not rom_file:
            raise FileNotFoundError(f"No ROM file found in {self.origin_dir}")
        
        print_info(f"Found ROM: {rom_file.name}")
        
        # Create temp directories
        ensure_directory(self.temp_dir)
        ensure_directory(self.exefs_dir)
        
        # Extract based on file type
        if rom_file.suffix == ".cia":
            self._extract_cia(rom_file)
        elif rom_file.suffix == ".3ds":
            self._extract_3ds(rom_file)
        elif rom_file.suffix == ".cxi":
            self._extract_cxi(rom_file)
        else:
            raise ValueError(f"Unsupported ROM format: {rom_file.suffix}")
        
        # Copy extracted files to output
        self._copy_extracted_files()
        
        # Clean up temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        
        print_success(f"✓ Extracted code.bin ({self._get_file_size(code_bin)})")
    
    def _extract_cia(self, rom_file: Path):
        """Extract .cia file"""
        print_info("Extracting CIA file...")
        
        if not self.ctrtool:
            raise RuntimeError("ctrtool not found - required for .cia extraction")
        
        # Extract contents from CIA
        contents_dir = self.temp_dir / "contents"
        ensure_directory(contents_dir)
        
        try:
            run_command([
                str(self.ctrtool),
                "--contents=" + str(contents_dir),
                str(rom_file)
            ])
        except Exception as e:
            raise RuntimeError(f"Failed to extract CIA contents: {e}")
        
        # Find the main content file (usually .0000.00000000)
        content_files = list(contents_dir.glob("*.0000.*"))
        if not content_files:
            content_files = list(contents_dir.glob("*"))
        
        if not content_files:
            raise RuntimeError("No content files found in CIA")
        
        content_file = content_files[0]
        print_info(f"Found content: {content_file.name}")
        
        # Extract CXI from content
        self._extract_cxi(content_file)
    
    def _extract_3ds(self, rom_file: Path):
        """Extract .3ds file"""
        print_info("Extracting 3DS file...")
        
        if self.dstool:
            self._extract_3ds_with_3dstool(rom_file)
        elif self.ctrtool:
            self._extract_3ds_with_ctrtool(rom_file)
        else:
            raise RuntimeError("Neither 3dstool nor ctrtool found")
    
    def _extract_3ds_with_3dstool(self, rom_file: Path):
        """Extract using 3dstool"""
        try:
            # Extract partition 0 (game partition)
            partition_file = self.temp_dir / "partition0.bin"
            
            run_command([
                str(self.dstool),
                "-x",  # extract
                "-t", "3ds",  # type
                "-f", str(rom_file),  # file
                "--header", str(self.temp_dir / "header.bin"),
                "-0", str(partition_file)  # partition 0 output
            ])
            
            # Extract CXI from partition
            self._extract_cxi(partition_file)
            
        except Exception as e:
            raise RuntimeError(f"Failed to extract 3DS file: {e}")
    
    def _extract_3ds_with_ctrtool(self, rom_file: Path):
        """Extract using ctrtool (fallback)"""
        try:
            # Extract NCSD (the container format)
            run_command([
                str(self.ctrtool),
                "-t", "ncsd",
                "--contents=" + str(self.temp_dir),
                str(rom_file)
            ])
            
            # Find and extract the CXI
            cxi_files = list(self.temp_dir.glob("*.cxi"))
            if not cxi_files:
                cxi_files = list(self.temp_dir.glob("*.0"))
            
            if cxi_files:
                self._extract_cxi(cxi_files[0])
            else:
                raise RuntimeError("No CXI found in 3DS file")
                
        except Exception as e:
            raise RuntimeError(f"Failed to extract 3DS file: {e}")
    
    def _extract_cxi(self, cxi_file: Path):
        """Extract ExeFS from CXI file"""
        print_info(f"Extracting CXI: {cxi_file.name}")
        
        if not self.ctrtool:
            raise RuntimeError("ctrtool not found - required for CXI extraction")
        
        # Ensure directories exist
        ensure_directory(self.exefs_dir)
        ensure_directory(self.romfs_dir)
        
        try:
            run_command([
                str(self.ctrtool),
                "-t", "cxi",
                "--exefsdir=" + str(self.exefs_dir),
                str(cxi_file)
            ])
            
            try:
                run_command([
                    str(self.ctrtool),
                    "-t", "cxi",
                    "--romfsdir=" + str(self.romfs_dir),
                    str(cxi_file)
                ], check=False)
            except Exception:
                pass
                
        except Exception as e:
            raise RuntimeError(f"Failed to extract CXI: {e}")
    
    def _copy_extracted_files(self):
        """Copy extracted files to output directory"""
        code_bin_src = self.exefs_dir / "code.bin"
        
        if not code_bin_src.exists():
            raise RuntimeError("code.bin not found in ExeFS")
        
        code_bin_dst = self.output_dir / "code.bin"
        shutil.copy2(code_bin_src, code_bin_dst)
        
        exefs_files = ["banner.bnr", "icon.icn", "logo.bcma.lz"]
        for filename in exefs_files:
            src = self.exefs_dir / filename
            if src.exists():
                dst = self.output_dir / filename
                shutil.copy2(src, dst)
        
        if self.romfs_dir.exists():
            romfs_dst = self.output_dir / "romfs"
            if romfs_dst.exists():
                shutil.rmtree(romfs_dst)
            shutil.copytree(self.romfs_dir, romfs_dst)
            print_info("✓ Extracted RomFS")
    
    def _get_file_size(self, file_path: Path) -> str:
        """Get human-readable file size"""
        size = file_path.stat().st_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def extract_specific_section(self, section_name: str) -> Optional[bytes]:
        """
        Extract a specific section from code.bin
        
        Args:
            section_name: Name of section to extract (e.g., ".text", ".data")
        
        Returns:
            Bytes of the section, or None if not found
        """
        code_bin = self.output_dir / "code.bin"
        if not code_bin.exists():
            return None
        
        with open(code_bin, 'rb') as f:
            data = f.read()
        
        # TODO: Parse ELF/NCCH header to find section
        logging.warning("Section extraction not yet implemented, returning entire code.bin")
        return data