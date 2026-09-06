"""
Unified entrypoint for File-Transformer.
- No arguments → launch CustomTkinter GUI
- Arguments present → run headless CLI conversion
"""
import sys


def main():
    # Strip the program name, check for remaining arguments
    args = sys.argv[1:]

    if args:
        # CLI mode
        from cli import run_cli
        sys.exit(run_cli(args))
    else:
        # GUI mode
        try:
            from gui.app import run_gui
            run_gui()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            # If GUI fails (e.g. no display), provide a helpful message
            print(f"\n[ERROR] Failed to launch GUI: {exc}", file=sys.stderr)
            print("  Try running with arguments for CLI mode:", file=sys.stderr)
            print("  python main.py -i <file> -f <format>", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
