import argparse
import sys
import traceback
from tools.scripts.extract_rom import ROMExtractor


def main():
    parser = argparse.ArgumentParser(
        description="Configure Animal Crossing: New Leaf decompilation project"
    )
    
    parser.add_argument(
        "--version",
        default="EGDP",
        help="Game version (default: EGDP for Europe)"
    )
    
    args = parser.parse_args()
    
    print("Animal Crossing: New Leaf - Project Configuration\n\n")
    try:
        extractor = ROMExtractor(args.version)
        success = extractor.extract()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()