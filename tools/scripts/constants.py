PROJECT_NAME = "acnl-decomp"
PROJECT_VERSION = "1.0.0"

SUPPORTED_REGIONS = ["EGDP", "EGDE", "EGDJ", "EGDK"]

ROM_EXTENSIONS = [".3ds"]

CODE_BASE_ADDRESS = 0x00100000
CODE_SIZE = 0x00400000

ARMCC_CPU = "MPCore"
ARMCC_OPTIMIZATION = "O3"
ARMCC_FPMODE = "fast"

TRANSLATION_UNIT_PATTERNS = {
    "__NamePattern__": r"([a-zA-Z0-9_]+)__"
}

# File structure
DIRECTORIES = {
    "source": "src",
    "include": "include",
    "library": "Library",
    "symbols": "Symbols",
    "data": "Data",
    "data_symbols": "DataSymbols",
    "tools": "tools",
    "origin": "origin",
    "build": "build",
}

COMPILER_FLAGS = {
    "common": [
        "--cpu=MPCore",
        "--fpmode=fast",
        "--apcs=/interwork",
        "--no_unaligned_access",
        "--fpu=vfpv2",
    ],
    "cxx": [
        "--cpp11",
        "--gnu",
        "--no_rtti",
        "--no_exceptions",
    ],
    "optimization": {
        "O0": ["-O0"],
        "O1": ["-O1"],
        "O2": ["-O2"],
        "O3": ["-O3"],
        "Os": ["-Ospace"],
        "Otime": ["-Otime"],
    }
}

WATCH_PATTERNS = [
    "*.c",
    "*.cpp",
]

IGNORE_PATTERNS = [
    "build/**/*",
    "orig/**/*",
    ".git/**/*",
    "__pycache__/**/*",
    "*.pyc",
]

SYMBOL_FORMATS = {
    "ida": {
        "function_pattern": r"^([0-9A-Fa-f]{8})\s+([TtWwVv])\s+(.+)$",
        "data_pattern": r"^([0-9A-Fa-f]{8})\s+([DdBbRr])\s+(.+)$",
    },
    "ghidra": {
        "function_pattern": r"^(.+)\s+([0-9A-Fa-f]{8})\s+Function",
        "data_pattern": r"^(.+)\s+([0-9A-Fa-f]{8})\s+Data",
    },
}