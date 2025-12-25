import sys
import argparse
from pathlib import Path

from tools.scripts.extractor import ROMExtractor
from tools.scripts.symbol_parser import SymbolParser
from tools.scripts.config_generator import ConfigGenerator
from tools.scripts.utils import setup_logging, print_header, print_success, print_error, print_info
from tools.scripts.constants import PROJECT_NAME, SUPPORTED_REGIONS


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Configure 3DS decompilation project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python configure.py                    # Use default EGDP region
  python configure.py --region EGDE      # Use EGDE region
  python configure.py --force            # Force re-extraction
  python configure.py --skip-extract     # Skip ROM extraction
  python configure.py --analyze-only     # Only run symbol analysis
        """
    )
    
    parser.add_argument(
        "--region",
        choices=SUPPORTED_REGIONS,
        default="EGDP",
        help="Region code to extract (default: EGDP)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-extraction even if files exist"
    )
    
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Skip ROM extraction (use existing files)"
    )
    
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only run symbol analysis, don't extract ROM"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--ida-symbols",
        type=Path,
        help="Path to IDA Pro symbol export file"
    )
    
    parser.add_argument(
        "--ghidra-symbols",
        type=Path,
        help="Path to Ghidra symbol export file"
    )
    
    return parser.parse_args()


def verify_tools(tools_dir: Path) -> bool:
    """Verify required tools are present"""
    required_tools = [
        "ctrtool.exe" if sys.platform == "win32" else "ctrtool",
        "3dstool.exe" if sys.platform == "win32" else "3dstool",
    ]
    
    missing_tools = []
    for tool in required_tools:
        tool_path = tools_dir / tool
        if not tool_path.exists():
            alt_tool = tool.replace(".exe", "")
            if not (tools_dir / alt_tool).exists():
                missing_tools.append(tool)
    
    if missing_tools:
        print_error(f"Missing required tools: {', '.join(missing_tools)}")
        print_info("Please place the required tools in the tools/ directory")
        print_info("Download from:")
        print_info("  - ctrtool: https://github.com/3DSGuy/Project_CTR")
        print_info("  - 3dstool: https://github.com/dnasdw/3dstool")
        return False
    
    return True


def main():
    """Main configuration process"""
    args = parse_arguments()
    setup_logging(args.verbose)
    
    print_header(f"{PROJECT_NAME} Configuration")
    print_info(f"Region: {args.region}")
    print()
    
    root_dir = Path(__file__).parent
    tools_dir = root_dir / "tools"
    origin_dir = root_dir / "origin" / args.region
    build_dir = root_dir / "build"
    symbols_dir = root_dir / "Symbols"
    
    for directory in [build_dir, origin_dir, symbols_dir]:
        directory.mkdir(exist_ok=True)
    
    if not args.skip_extract and not args.analyze_only:
        print_info("Verifying tools...")
        if not verify_tools(tools_dir):
            return 1
        print_success("(SUCCESS) All required tools found")
        print()
    
    if not args.skip_extract and not args.analyze_only:
        print_header("Step 1: ROM Extraction")
        extractor = ROMExtractor(tools_dir, origin_dir, origin_dir)
        
        if not extractor.verify_rom_exists():
            print_error(f"No ROM found in {origin_dir}")
            print_info("Please place your .3ds or .cia file in the appropriate origin directory")
            return 1
        
        try:
            extractor.extract(force=args.force)
            print_success("(SUCCESS) ROM extraction complete")
            print()
        except Exception as e:
            print_error(f"ROM extraction failed: {e}")
            return 1
    else:
        print_info("Skipping ROM extraction")
        print()
    
    print_header("Step 2: Symbol Analysis")
    parser = SymbolParser(origin_dir, symbols_dir)
    
    if args.ida_symbols:
        print_info(f"Loading IDA symbols from {args.ida_symbols}")
        parser.load_ida_symbols(args.ida_symbols)
    
    if args.ghidra_symbols:
        print_info(f"Loading Ghidra symbols from {args.ghidra_symbols}")
        parser.load_ghidra_symbols(args.ghidra_symbols)
    
    if not args.ida_symbols and not args.ghidra_symbols:
        print_info("No external symbols provided, performing basic analysis...")
        parser.analyze_code_bin()
    
    parser.export_symbols()
    print_success(f"(SUCCESS) Found {parser.get_symbol_count()} symbols")
    print()
    
    if args.analyze_only:
        print_success("Analysis complete!")
        return 0
    
    print_header("Step 3: Configuration Generation")
    generator = ConfigGenerator(root_dir, origin_dir, build_dir, args.region)
    
    print_info("Generating objdiff.json...")
    units = parser.get_symbols_as_single_unit_per_symbol()
    generator.generate_objdiff_config(units)
    print_success("(SUCCESS) Generated objdiff.json")
    
    print_info("Generating diff_settings.py...")
    generator.generate_diff_settings()
    print_success("(SUCCESS) Generated diff_settings.py")
    
    print_info("Generating CMakeLists.txt...")
    generator.generate_cmake_config(units)
    print_success("(SUCCESS) Generated CMakeLists.txt")
    
    print_info("Generating ARMCC.cmake...")
    generator.generate_armcc_config()
    print_success("(SUCCESS) Generated ARMCC.cmake")
    
    print()
    print_header("Configuration Complete!")
    print_success("Your decompilation workspace is ready!")
    print_info(f"Total symbols: {parser.get_symbol_count()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())