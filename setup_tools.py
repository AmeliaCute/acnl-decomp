"""
Tool installer for ACNL decompilation project
Downloads and sets up required tools automatically
"""

import argparse
import json
import platform
import stat
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path


class ToolsInstaller:
    def __init__(self, force: bool = False):
        self.config_path = Path("config/tools.json")
        self.tools_dir = Path("tools") / "bin"
        self.tools_dir.mkdir(exist_ok=True)
        self.force = force
        self.system = platform.system()
        
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")
            sys.exit(1)
    
    def check_tool_exists(self, tool_name: str) -> bool:
        tool_path = self.tools_dir / tool_name
        tool_path_exe = self.tools_dir / (tool_name + ".exe")
        
        if tool_path.exists() or tool_path_exe.exists():
            return True
        
        which_cmd = "where" if self.system == "Windows" else "which"
        result = subprocess.run([which_cmd, tool_name], capture_output=True)
        return result.returncode == 0
    
    def download_file(self, url: str, destination: Path) -> bool:
        print(f"[INFO] Downloading from: {url}")
        
        def progress_hook(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\r[INFO] Progress: {percent}%")
                sys.stdout.flush()
        
        try:
            urllib.request.urlretrieve(url, destination, reporthook=progress_hook)
            print()
            return True
        except Exception as e:
            print(f"\n[ERROR] Download failed: {e}")
            return False
    
    def extract_archive(self, archive_path: Path, tool_name: str) -> bool:
        try:
            print(f"[INFO] Extracting {tool_name}...")
            
            if archive_path.suffix == '.zip' or archive_path.name.endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(self.tools_dir)
            elif archive_path.name.endswith('.tar.gz') or archive_path.name.endswith('.tgz'):
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(self.tools_dir)
            else:
                print(f"[ERROR] Unknown archive format: {archive_path}")
                return False
            
            return True
        except Exception as e:
            print(f"[ERROR] Extraction failed: {e}")
            return False
    
    def make_executable(self, tool_path: Path):
        if self.system != "Windows":
            try:
                current_permissions = tool_path.stat().st_mode
                tool_path.chmod(current_permissions | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except Exception as e:
                print(f"[WARNING] Could not make executable: {e}")
    
    def install_tool(self, tool_config: dict) -> bool:
        tool_name = tool_config['name']
        
        if not self.force and self.check_tool_exists(tool_name):
            print(f"[INFO] {tool_name} already installed")
            return True
        
        print(f"[INFO] Installing {tool_name}...")
        
        urls = tool_config.get('urls', {})
        if self.system not in urls:
            print(f"[ERROR] No download URL for platform: {self.system}")
            print(f"[INFO] Please install manually from: {tool_config['repository']}")
            return False
        
        url = urls[self.system]
        
        is_archive = False
        is_direct_binary = False
        
        if url.endswith('.zip'):
            archive_ext = '.zip'
            is_archive = True
        elif url.endswith('.tar.gz') or url.endswith('.tgz'):
            archive_ext = '.tar.gz'
            is_archive = True
        elif url.endswith('.exe'):
            archive_ext = '.exe'
            is_direct_binary = True
        else:
            archive_ext = ''
            is_direct_binary = True
        
        if is_direct_binary and not archive_ext:
            download_path = self.tools_dir / (tool_name + (".exe" if self.system == "Windows" else ""))
        else:
            download_path = self.tools_dir / f"{tool_name}{archive_ext}"
        
        if not self.download_file(url, download_path):
            return False
        
        if is_archive:
            if not self.extract_archive(download_path, tool_name):
                download_path.unlink(missing_ok=True)
                return False
            download_path.unlink()
            
            tool_path = self.tools_dir / (tool_name + (".exe" if self.system == "Windows" else ""))
            
            if not tool_path.exists():
                for file in self.tools_dir.rglob(tool_name + ("*" if self.system == "Windows" else "")):
                    if file.is_file() and (file.name == tool_name or file.name == f"{tool_name}.exe"):
                        file.rename(tool_path)
                        break
            
            if not tool_path.exists():
                print(f"[ERROR] {tool_name} not found after extraction")
                return False
        else:
            tool_path = download_path
        
        if self.system != "Windows":
            self.make_executable(tool_path)
        
        if tool_path.exists():
            size_kb = tool_path.stat().st_size / 1024
            print(f"[SUCCESS] {tool_name} installed ({size_kb:.2f} KB)")
            return True
        else:
            print(f"[ERROR] {tool_name} installation failed")
            return False
    
    def verify_installation(self) -> bool:
        """Verify all tools are installed"""
        print("\n[INFO] Verifying installation...")
        
        all_good = True
        for tool_config in self.config['tools']:
            tool_name = tool_config['name']
            if self.check_tool_exists(tool_name):
                print(f"[OK] {tool_name}")
            else:
                print(f"[MISSING] {tool_name}")
                all_good = False
        
        return all_good
    
    def install_all(self) -> bool:
        """Install all tools"""
        print("=" * 32)
        print("Animal Crossing: New Leaf - Tool Setup")
        print("=" * 32)
        print(f"Platform: {self.system} ({platform.machine()})")
        print()
        
        if self.system not in ["Linux", "Darwin", "Windows"]:
            print(f"[ERROR] Unsupported platform: {self.system}")
            print("[INFO] Supported platforms: Linux, macOS, Windows")
            self._print_manual_install()
            return False
        
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Tools directory: {self.tools_dir}")
        print()
        
        if not self.force:
            all_exist = all(self.check_tool_exists(t['name']) for t in self.config['tools'])
            if all_exist:
                print("[INFO] All tools already installed")
                print("[INFO] Use --force to reinstall")
                return True
        
        success_count = 0
        for tool_config in self.config['tools']:
            if self.install_tool(tool_config):
                success_count += 1
            else:
                print(f"[ERROR] Failed to install {tool_config['name']}")
                print(f"[INFO] Download manually from: {tool_config['repository']}")
            print()
        
        if self.verify_installation():
            print("\n" + "=" * 32)
            print("[SUCCESS] All dependencies installed successfully!")
            print("=" * 32)
            print("\nNext steps:")
            print("  1. Place your ROM in origin/EGDP/")
            print("  2. Run: python configure.py")
            return True
        else:
            print("\n" + "=" * 32)
            print("[WARNING] Some dependencies are missing")
            print("=" * 32)
            self._print_manual_install()
            return False
    
    def _print_manual_install(self):
        """Print manual installation instructions"""
        print("\nManual installation:")
        for tool_config in self.config['tools']:
            print(f"  - {tool_config['name']}: {tool_config['repository']}")


def main():
    parser = argparse.ArgumentParser(
        description="Download and setup extraction tools for ACNL decompilation"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall even if tools exist"
    )
    
    args = parser.parse_args()
    installer = ToolsInstaller(force=args.force)
    
    success = installer.install_all()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()