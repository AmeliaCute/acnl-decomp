import argparse
import json
import platform
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


class ToolsInstaller:
    def __init__(self, force: bool = False):
        self.config_path = Path("config/Tools.json")
        self.Tools_dir = Path("Tools")
        self.force = force
        self.system = platform.system()
        
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Tools] failed to load config: {e}")
            sys.exit(1)
    
    def check_tool_exists(self, tool_name: str) -> bool:
        tool_path = self.Tools_dir / (tool_name + (".exe" if self.system == "Windows" else ""))
        
        if tool_path.exists():
            return True
        
        which_cmd = "where" if self.system == "Windows" else "which"
        result = subprocess.run([which_cmd, tool_name], capture_output=True)
        return result.returncode == 0
    
    def download_file(self, url: str, destination: Path) -> bool:
        print(f"[Tools] downloading from: {url}")
        
        def progress_hook(count, block_size, total_size):
            if total_size > 0:
                percent = int(count * block_size * 100 / total_size)
                sys.stdout.write(f"\n[Tools] progress: {percent}%")
                sys.stdout.flush()
        
        try:
            urllib.request.urlretrieve(url, destination, reporthook=progress_hook)
            print()
            return True
        except Exception as e:
            print(f"[Tools] download failed: {e}")
            return False
    
    def extract_tool(self, zip_path: Path, tool_name: str) -> bool:
        try:
            print(f"[Tools] extracting {tool_name}...")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.Tools_dir)
            
            return True
        except Exception as e:
            print(f"[Tools] extraction failed: {e}")
            return False
    
    def make_executable(self, tool_path: Path):
        if self.system != "Windows":
            try:
                current_permissions = tool_path.stat().st_mode
                tool_path.chmod(current_permissions | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            except Exception as e:
                print(f"[Tools] could not make executable: {e}")
    
    def install_tool(self, tool_config: dict) -> bool:
        tool_name = tool_config['name']
        tool_path = self.Tools_dir / (tool_name + (".exe" if self.system == "Windows" else ""))
        
        if not self.force and tool_path.exists():
            print(f"[Tools] {tool_name} already installed")
            return True
        
        print(f"[Tools] Installing {tool_name}...")
        
        urls = tool_config.get('urls', {})
        if self.system not in urls:
            print(f"[Tools] no download URL for platform: {self.system}")
            print(f"[Tools] please install manually from: {tool_config['repository']}")
            return False
        
        url = urls[self.system]
        
        zip_path = self.Tools_dir / f"{tool_name}_download.zip"
        if not self.download_file(url, zip_path):
            return False
        
        if not self.extract_tool(zip_path, tool_name):
            zip_path.unlink(missing_ok=True)
            return False
        
        zip_path.unlink()
        
        if self.system != "Windows":
            self.make_executable(tool_path)
        
        if tool_path.exists():
            size_kb = tool_path.stat().st_size / 1024
            print(f"[Tools] {tool_name} installed ({size_kb:.2f} KB)")
            return True
        else:
            print(f"[Tools] {tool_name} not found after extraction")
            return False
    
    def verify_installation(self) -> bool:
        print("[Tools] verifying installation")
        
        all_good = True
        for tool_config in self.config['tools']:
            tool_name = tool_config['name']
            if self.check_tool_exists(tool_name):
                print(f"[Tools] {tool_name} is available")
            else:
                print(f"[Tools] {tool_name} is missing")
                all_good = False
        
        return all_good
    
    def install_all(self) -> bool:
        print("[Tools] Animal Crossing: New Leaf - Dependencies Setup")
        print(f"[Tools] platform: {self.system} ({platform.machine()})")
        
        if self.system not in ["Linux", "Darwin", "Windows"]:
            print(f"[Tools] unsupported platform: {self.system}")
            print("[Tools] supported platforms: Linux, macOS (Darwin), Windows")
            self._print_manual_install()
            return False
        
        self.Tools_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Tools] Tools directory: {self.Tools_dir}")
        
        if not self.force:
            all_exist = all(self.check_tool_exists(t['name']) for t in self.config['tools'])
            if all_exist:
                print("[Tools] all Tools already installed")
                return True
        
        success_count = 0
        for tool_config in self.config['tools']:
            if self.install_tool(tool_config):
                success_count += 1
            else:
                print(f"[Tools] failed to install {tool_config['name']}")
                print(f"[Tools] download manually from: {tool_config['repository']}")
        
        if self.verify_installation():
            print("[Tools] all dependencies installed successfully!")
            return True
        else:
            print("[Tools] some dependencies are missing")
            self._print_manual_install()
            return False
    
    def _print_manual_install(self):
        print("[Tools] please install missing Tools manually:")
        for tool_config in self.config['tools']:
            print(f"[Tools] - {tool_config['name']}: {tool_config['repository']}")


def main():
    parser = argparse.ArgumentParser(description="download and setup extraction Tools for ACNL decompilation")
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reinstall even if Tools exist"
    )
    
    args = parser.parse_args()
    installer = ToolsInstaller(force=args.force)
    
    success = installer.install_all()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()