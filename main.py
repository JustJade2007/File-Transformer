"""
Unified entrypoint for File-Transformer.
- No arguments → launch CustomTkinter GUI
- Arguments present → run headless CLI conversion
"""
import os
import sys

# PyInstaller windowed mode (--noconsole / --windowed) leaves sys.stdout and sys.stderr as None.
# Redirect them to os.devnull so library logging or prints never fail with AttributeError.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")


def main():
    # Strip the program name, check for remaining arguments
    args = sys.argv[1:]

    if args:
        # CLI mode: attach to existing terminal console if available on Windows
        if sys.platform == "win32":
            import ctypes
            if ctypes.windll.kernel32.AttachConsole(-1):
                try:
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                except Exception:
                    pass
        from cli import run_cli
        sys.exit(run_cli(args))
    else:
        # GUI mode
        try:
            from gui.app import run_gui
            run_gui()
            sys.exit(0)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            try:
                print(f"\n[ERROR] Failed to launch GUI: {exc}", file=sys.stderr)
                print("  Try running with arguments for CLI mode:", file=sys.stderr)
                print("  python main.py -i <file> -f <format>", file=sys.stderr)
            except Exception:
                pass
            sys.exit(1)


if __name__ == "__main__":
    main()

