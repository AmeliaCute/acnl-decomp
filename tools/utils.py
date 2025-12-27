from pathlib import Path
import shutil
import sys
from typing import Optional


def find_tool(tool_name: str) -> Optional[Path]:
    tools_dir = Path(".") / "tools" / "bin"
  
    if sys.platform == "win32":
        tool_path = tools_dir / f"{tool_name}.exe"
        if tool_path.exists():
            return tool_path
    
    tool_path = tools_dir / tool_name
    if tool_path.exists():
        return tool_path
    
    for ext in [".py", ".sh", ".bat"]:
        tool_path = tools_dir / f"{tool_name}{ext}"
        if tool_path.exists():
            return tool_path
    
    system_path = shutil.which(tool_name)
    if system_path:
        return Path(system_path)
    
    return None
  
  
def parse_hex(s: str) -> int:
    s = s.strip().lower()
    if s.endswith("h"):
        s = s[:-1]
    if s.startswith("0x"):
        s = s[2:]
    return int(s, 16)