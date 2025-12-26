"""
Utility functions for the configuration system
"""

import sys
import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = False,
    check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the result"""
    logging.debug(f"Running command: {' '.join(str(c) for c in cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(str(c) for c in cmd)}")
        if e.stdout:
            logging.debug(f"stdout: {e.stdout}")
        if e.stderr:
            logging.debug(f"stderr: {e.stderr}")
        raise


def find_tool(tools_dir: Path, tool_name: str) -> Optional[Path]:
    """
    Find a tool in the tools directory or system PATH
    Handles platform differences (Windows .exe extensions)
    """
    # Check in tools directory with .exe on Windows
    if sys.platform == "win32":
        tool_path = tools_dir / f"{tool_name}.exe"
        if tool_path.exists():
            return tool_path
    
    # Check without extension
    tool_path = tools_dir / tool_name
    if tool_path.exists():
        return tool_path
    
    # Check common script extensions
    for ext in [".py", ".sh", ".bat"]:
        tool_path = tools_dir / f"{tool_name}{ext}"
        if tool_path.exists():
            return tool_path
    
    # Check system PATH
    system_path = shutil.which(tool_name)
    if system_path:
        return Path(system_path)
    
    return None


def format_address(addr: int) -> str:
    """Format an address as 8-character hex string"""
    return f"{addr:08X}"


def parse_address(addr_str: str) -> int:
    """Parse an address string to integer"""
    addr_str = addr_str.replace("0x", "").replace("0X", "")
    return int(addr_str, 16)


def format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary"""
    path.mkdir(parents=True, exist_ok=True)
    return path