import json
from pathlib import Path
from typing import Dict, List

from tools.scripts.constants import (
    PROJECT_NAME, WATCH_PATTERNS, IGNORE_PATTERNS,
    COMPILER_FLAGS, ARMCC_CPU, ARMCC_OPTIMIZATION,
    DIRECTORIES
)
from tools.scripts.utils import ensure_directory


class ConfigGenerator:
    """Generate configuration files for the decompilation project"""
    
    def __init__(self, root_dir: Path, orig_dir: Path, build_dir: Path, region: str):
        self.root_dir = root_dir
        self.orig_dir = orig_dir
        self.build_dir = build_dir
        self.region = region
        self.source_dir = root_dir / DIRECTORIES["source"]
        self.include_dir = root_dir / DIRECTORIES["include"]
        
        ensure_directory(self.source_dir)
        ensure_directory(self.include_dir)
    
    def generate_objdiff_config(self, translation_units: Dict[str, List]):
        units = []
        
        for unit_name, symbols in translation_units.items():
            
            has_cpp = any("std::" in s.demangled or "::" in s.demangled for s in symbols)
            ext = "cpp" if has_cpp else "c"
            
            unit = {
                "name": unit_name,
                "target_path": str(self.orig_dir / "code.bin"),
                "base_path": str(self.build_dir / "CMakeFiles" / f"{PROJECT_NAME}.dir" / "src" / f"{unit_name}.{ext}.o"),
            }
            
            if len(symbols) > 0:
                unit["metadata"] = {
                    "complete": False,
                    "symbol_count": len(symbols),
                    "source_path": str(self.root_dir / "src" / f"{unit_name}.{ext}"),
                    "function_count": len([s for s in symbols if s.type == "function"]),
                }
            
            units.append(unit)
        
        config = {
            "$schema": "https://raw.githubusercontent.com/encounter/objdiff/main/config.schema.json",
            "custom_make": "cmake",
            "custom_args": [
                "--build",
                "build"
            ],
            "build_target": False,
            "build_base": True,
            "watch_patterns": WATCH_PATTERNS,
            "ignore_patterns": IGNORE_PATTERNS,
            "units": units
        }
        
        output_file = self.root_dir / "objdiff.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    
    def generate_diff_settings(self):
        content = f'''#!/usr/bin/env python3
"""
objdiff Python configuration
Advanced settings for objdiff integration
"""


def apply(config):
    """
    Apply custom configuration to objdiff
    
    Args:
        config: Configuration dictionary to modify
    """
    # Architecture settings
    config["arch"] = "arm"
    config["platform"] = "3ds"
    
    # Base addresses
    config["base_addr"] = 0x00100000
    
    # Binary paths
    config["baseimg_format"] = "raw"
    config["baseimg"] = "origin/{self.region}/code.bin"
    config["myimg"] = "build/{PROJECT_NAME}.elf"
    
    # Map file for symbol resolution
    config["mapfile"] = "build/{PROJECT_NAME}.map"
    
    # Source directories
    config["source_directories"] = [
        "Source",
        "Include",
        "Library",
    ]
    
    # Compiler settings
    config["compiler"] = "armcc"
    config["compiler_flags"] = {' '.join(f'"{flag}"' for flag in COMPILER_FLAGS["common"])}
    
    # Symbol processing
    config["demangle"] = True
    config["symbol_style"] = "msvc"  # or "gnu" for GCC-style
    
    # Diff display settings
    config["show_line_numbers"] = True
    config["show_branch_targets"] = True
    config["show_data_refs"] = True
    
    # Color scheme (optional)
    config["colors"] = {{
        "match": "#00FF00",
        "mismatch": "#FF0000",
        "missing": "#FFFF00",
    }}
'''
        
        output_file = self.root_dir / "diff_settings.py"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def generate_cmake_config(self, translation_units: Dict[str, List]):
        """
        Generate CMakeLists.txt
        
        Args:
            translation_units: Dictionary of translation unit name to symbols
        """
        source_files = []
        for unit_name, symbols in translation_units.items():
            
            has_cpp = any("std::" in s.demangled or "::" in s.demangled for s in symbols)
            ext = "cpp" if has_cpp else "c"
            source_files.append(f"{DIRECTORIES['source']}/{unit_name}.{ext}")
        
        content = f'''cmake_minimum_required(VERSION 3.15)

# Set toolchain file - MUST be before project() to take effect
set(CMAKE_TOOLCHAIN_FILE "${{CMAKE_CURRENT_SOURCE_DIR}}/ARMCC.cmake")

project({PROJECT_NAME} CXX C ASM)

# Set toolchain file again (redundant but safe)
set(CMAKE_TOOLCHAIN_FILE "${{CMAKE_CURRENT_SOURCE_DIR}}/ARMCC.cmake")

# Project version
set(PROJECT_VERSION "1.0.0")
set(GAME_REGION "{self.region}")

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${{CMAKE_BINARY_DIR}}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${{CMAKE_BINARY_DIR}}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${{CMAKE_BINARY_DIR}}")

# Create main executable
add_executable({PROJECT_NAME})

# Add source files
target_sources({PROJECT_NAME} PRIVATE
    # Main sources
'''
        
        for src_file in sorted(source_files):
            content += f"    {src_file}\n"
        
        content += f''')

# Include directories
target_include_directories({PROJECT_NAME} PRIVATE
    {DIRECTORIES['include']}
    #{DIRECTORIES['library']}/sead/include
    #{DIRECTORIES['library']}/NintendoSDK/include
)

# Compiler definitions
target_compile_definitions({PROJECT_NAME} PRIVATE
    GAME_REGION_${{GAME_REGION}}
    ARM_ARCH_ARMv6=1
    __3DS__=1
)

# Common compiler flags
target_compile_options({PROJECT_NAME} PRIVATE
'''
        
        for flag in COMPILER_FLAGS["common"]:
            content += f'    "{flag}"\n'
        
        content += f''')

# C++ specific flags
target_compile_options({PROJECT_NAME} PRIVATE
    $<$<COMPILE_LANGUAGE:CXX>:
'''
        
        for flag in COMPILER_FLAGS["cxx"]:
            content += f'        "{flag}"\n'
        
        content += f'''    >
)

# Optimization flags
target_compile_options({PROJECT_NAME} PRIVATE
    {' '.join(COMPILER_FLAGS["optimization"][ARMCC_OPTIMIZATION])}
)

# Linker flags
target_link_options({PROJECT_NAME} PRIVATE
    --cpu={ARMCC_CPU}
    --map
    --list=${{CMAKE_BINARY_DIR}}/{PROJECT_NAME}.map
    --entry=_start
)

# Generate symbols for objdiff
add_custom_command(TARGET {PROJECT_NAME} POST_BUILD
    COMMAND ${{CMAKE_COMMAND}} -E echo "Build complete: {PROJECT_NAME}"
    COMMENT "Finalizing build..."
)

# Install target (optional)
install(TARGETS {PROJECT_NAME}
    RUNTIME DESTINATION bin
)
'''
        
        output_file = self.root_dir / "CMakeLists.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def generate_armcc_config(self):
        """Generate ARMCC.cmake toolchain file"""
        content = '''# Dev kit pro arm (ARMCC) Toolchain File
# For use with 3DS decompilation projects

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR ARM)

# Detect host system for executable extension
if(CMAKE_HOST_WIN32)
    set(TOOL_EXT ".exe")
else()
    set(TOOL_EXT "")
endif()

# Specify the cross compiler
# UPDATE THIS PATH to point to your ARM compiler installation
set(ARMCC_ROOT_PATH "$ENV{DEVKITPROARM_PATH}" CACHE PATH "Dev kit pro arm root path")

if(NOT ARMCC_ROOT_PATH)
    message(FATAL_ERROR 
        "DEVKITPROARM_PATH environment variable not set. "
        "Please set it to your ARM Compiler installation directory, "
        "e.g., C:/Program Files/ARM/RVCT/Programs/5.06/761/win_32-pentium"
    )
endif()

# Compiler executables
set(CMAKE_C_COMPILER "${ARMCC_ROOT_PATH}/armcc${TOOL_EXT}")
set(CMAKE_CXX_COMPILER "${ARMCC_ROOT_PATH}/armcc${TOOL_EXT}")
set(CMAKE_ASM_COMPILER "${ARMCC_ROOT_PATH}/armasm${TOOL_EXT}")
set(CMAKE_AR "${ARMCC_ROOT_PATH}/armar${TOOL_EXT}")
set(CMAKE_LINKER "${ARMCC_ROOT_PATH}/armlink${TOOL_EXT}")

# Check if compiler exists
if(NOT EXISTS "${CMAKE_C_COMPILER}")
    message(FATAL_ERROR "ARM Compiler not found at: ${CMAKE_C_COMPILER}")
endif()

# Compiler identification
set(CMAKE_C_COMPILER_ID "ARMCC")
set(CMAKE_CXX_COMPILER_ID "ARMCC")

# Skip compiler tests (cross-compilation)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(CMAKE_C_COMPILER_WORKS 1)
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_ASM_COMPILER_WORKS 1)

# C++ standard
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Object file extension
set(CMAKE_C_OUTPUT_EXTENSION .o)
set(CMAKE_CXX_OUTPUT_EXTENSION .o)
set(CMAKE_ASM_OUTPUT_EXTENSION .o)

# Executable suffix
set(CMAKE_EXECUTABLE_SUFFIX .elf)

# Search for programs in the build host directories
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)

# Search for libraries and headers in the target directories
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# Platform-specific settings
set(CMAKE_SYSTEM_VERSION 1)
set(CMAKE_CROSSCOMPILING TRUE)

# Custom compile commands for ARMCC
set(CMAKE_C_COMPILE_OBJECT
    "<CMAKE_C_COMPILER> <DEFINES> <INCLUDES> <FLAGS> -o <OBJECT> -c <SOURCE>")
set(CMAKE_CXX_COMPILE_OBJECT
    "<CMAKE_CXX_COMPILER> <DEFINES> <INCLUDES> <FLAGS> -o <OBJECT> -c <SOURCE>")

# Custom link command
set(CMAKE_CXX_LINK_EXECUTABLE
    "<CMAKE_LINKER> <FLAGS> <CMAKE_CXX_LINK_FLAGS> <LINK_FLAGS> <OBJECTS> -o <TARGET> <LINK_LIBRARIES>")

# Disable response files (ARMCC doesn't support them in older versions)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_INCLUDES OFF)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_INCLUDES OFF)

message(STATUS "Dev kit pro arm toolchain configured")
message(STATUS "Compiler path: ${CMAKE_C_COMPILER}")
'''
        
        output_file = self.root_dir / "ARMCC.cmake"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def generate_stub_sources(self, translation_units: Dict[str, List]):
        """
        Generate stub source files for each translation unit
        
        Args:
            translation_units: Dictionary of translation unit name to symbols
        """
        ensure_directory(self.source_dir)
        
        for unit_name, symbols in translation_units.items():
            has_cpp = any("std::" in s.demangled or "::" in s.demangled for s in symbols)
            ext = "cpp" if has_cpp else "c"
            
            source_file = self.source_dir / f"{unit_name}.{ext}"
            
            if source_file.exists():
                continue
            
            content = self._generate_stub_content(unit_name, symbols, ext)
            
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _generate_stub_content(self, unit_name: str, symbols: List, ext: str) -> str:
        """Generate stub source file content"""
        content = f"""/*
 * {unit_name}.{ext}
 * Auto-generated stub file
 * * Contains {len(symbols)} symbols
 * Functions: {len([s for s in symbols if s.type == 'function'])}
 * Data: {len([s for s in symbols if s.type == 'data'])}
 */

"""
        
        if ext == "cpp":
            content += '#include <cstdint>\n\n'
        else:
            content += '#include <stdint.h>\n\n'
        
        for symbol in symbols:
            if symbol.type == "function":
                content += f"// {symbol.demangled}\n"
                content += f"// Address: {symbol.address:#010x}\n"
                content += f"void {symbol.name}() {{\n"
                content += f"    // TODO: Implement {symbol.demangled}\n"
                content += "}}\n\n"
        
        return content