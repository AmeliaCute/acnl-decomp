"""
Utility functions for the configuration system
"""

import sys
import logging
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional


class Color:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
    @classmethod
    def disable(cls):
        """Disable colors (for Windows compatibility)"""
        cls.HEADER = ''
        cls.OKBLUE = ''
        cls.OKCYAN = ''
        cls.OKGREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''


# Disable colors on Windows unless using a modern terminal
if sys.platform == "win32" and not sys.stdout.isatty():
    Color.disable()


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )


def print_header(text: str):
    """Print a formatted header"""
    print(f"{Color.BOLD}{Color.OKCYAN}{'=' * 60}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.OKCYAN}{text:^60}{Color.ENDC}")
    print(f"{Color.BOLD}{Color.OKCYAN}{'=' * 60}{Color.ENDC}")


def print_success(text: str):
    """Print success message"""
    print(f"{Color.OKGREEN}{text}{Color.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Color.FAIL}ERROR: {text}{Color.ENDC}", file=sys.stderr)


def print_warning(text: str):
    """Print warning message"""
    print(f"{Color.WARNING}WARNING: {text}{Color.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Color.OKBLUE}{text}{Color.ENDC}")


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    capture_output: bool = False,
    check: bool = True
) -> subprocess.CompletedProcess:
    """
    Run a command and return the result
    
    Args:
        cmd: Command and arguments as list
        cwd: Working directory
        capture_output: Capture stdout/stderr
        check: Raise exception on non-zero exit
    
    Returns:
        CompletedProcess instance
    """
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
        print_error(f"Command failed: {' '.join(str(c) for c in cmd)}")
        if e.stdout:
            logging.debug(f"stdout: {e.stdout}")
        if e.stderr:
            logging.debug(f"stderr: {e.stderr}")
        raise


def find_tool(tools_dir: Path, tool_name: str) -> Optional[Path]:
    """
    Find a tool in the tools directory, handling platform differences
    and system path lookups (useful for devkitPro tools).
    
    Args:
        tools_dir: Directory containing tools
        tool_name: Base name of the tool
    
    Returns:
        Path to tool if found, None otherwise
    """
    if sys.platform == "win32":
        tool_path = tools_dir / f"{tool_name}.exe"
        if tool_path.exists():
            return tool_path
    
    tool_path = tools_dir / tool_name
    if tool_path.exists():
        return tool_path
    
    alternates = [
        f"{tool_name}.py",
        f"{tool_name}.sh",
        f"{tool_name}.bat",
    ]
    
    for alt in alternates:
        tool_path = tools_dir / alt
        if tool_path.exists():
            return tool_path
            
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


def demangle_symbol(symbol: str) -> str:
    """
    Attempt to demangle a C++ symbol name
    
    Args:
        symbol: Mangled symbol name
    
    Returns:
        Demangled name or original if demangling fails
    """
    if not symbol.startswith("_Z"):
        return symbol
    
    try:
        result = subprocess.run(
            ["c++filt", symbol],
            capture_output=True,
            text=True,
            timeout=1
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return symbol


def group_symbols_by_namespace(symbols: List[dict]) -> dict:
    """
    Group symbols by their namespace/class
    
    Args:
        symbols: List of symbol dictionaries
    
    Returns:
        Dictionary mapping namespace to symbols
    """
    groups = {}
    
    for symbol in symbols:
        name = symbol.get("name", "")
        
        if name.startswith("_ZN"):
            parts = name.split("N")[1].split("E")[0] if "E" in name else ""
            namespace = parts[:4] if len(parts) >= 4 else "Unknown"
        else:
            namespace = "Global"
        
        if namespace not in groups:
            groups[namespace] = []
        groups[namespace].append(symbol)
    
    return groups


def calculate_progress(total: int, matched: int) -> float:
    """Calculate percentage progress"""
    if total == 0:
        return 0.0
    return (matched / total) * 100.0


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