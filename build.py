"""
PyInstaller build script for File-Transformer.
Produces both:
  1. dist/FileTransformer.exe  (one-file portable)
  2. dist/FileTransformer/     (one-dir bundle, instant launch)
"""
import os
import subprocess
import sys
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist")
BUILD_DIR = os.path.join(ROOT, "build")
ICON_PATH = os.path.join(ROOT, "assets", "icon.ico")


def get_pyinstaller_base_args(name: str, one_file: bool) -> list:
    """Build shared PyInstaller arguments."""
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", name,
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--noconfirm",
        "--clean",
        # Collect all required packages
        "--collect-all", "customtkinter",
        "--collect-all", "tkinterdnd2",
        "--collect-data", "pypdf",
        # Hidden imports for dynamic loading
        "--hidden-import", "PIL._imaging",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "pypdf",
        "--hidden-import", "docx",
        "--hidden-import", "openpyxl",
        "--hidden-import", "yaml",
        "--hidden-import", "fontTools",
        "--hidden-import", "fontTools.ttLib",
        "--hidden-import", "markdown",
        "--hidden-import", "tkinterdnd2",
        # Windows subsystem — window mode silences console so no command prompt opens
        "--noconsole",
    ]

    if os.path.isfile(ICON_PATH):
        args += ["--icon", ICON_PATH]

    if one_file:
        args.append("--onefile")
    else:
        args.append("--onedir")

    args.append(os.path.join(ROOT, "main.py"))
    return args


def remove_readonly_and_delete(path: str):
    if not os.path.exists(path):
        return
    import stat
    def on_err(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except Exception:
            pass
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=on_err)
    else:
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            os.remove(path)
        except Exception:
            pass


def build(one_file: bool, suffix: str = ""):
    name = f"FileTransformer{suffix}"
    # Ensure build workpath and dist target don't have read-only locks
    if sys.platform == "win32":
        try:
            subprocess.run(["cmd.exe", "/c", f"attrib -r -s -h /s /d \"{BUILD_DIR}\\*\" & attrib -r -s -h \"{BUILD_DIR}\""], capture_output=True)
            subprocess.run(["cmd.exe", "/c", f"attrib -r -s -h /s /d \"{DIST_DIR}\\*\" & attrib -r -s -h \"{DIST_DIR}\""], capture_output=True)
        except Exception:
            pass

    target_dir = os.path.join(DIST_DIR, name)
    target_exe = os.path.join(DIST_DIR, f"{name}.exe")
    remove_readonly_and_delete(target_dir)
    remove_readonly_and_delete(target_exe)

    args = get_pyinstaller_base_args(name, one_file)
    mode = "onefile" if one_file else "onedir"
    print("\n" + "=" * 60)
    print("  Building " + name + " (" + mode + ")...")
    print("=" * 60 + "\n")
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        print("[ERROR] PyInstaller build failed for " + name + ".")
        sys.exit(result.returncode)
    print("\n[OK] " + name + " built successfully.")



def main():
    print("File-Transformer Build Script")
    print("-" * 40)

    # Ensure assets/icon.ico placeholder exists so build does not fail
    assets_dir = os.path.join(ROOT, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    if not os.path.isfile(ICON_PATH):
        print("[INFO] No icon.ico found in assets/ -- building without icon.")

    # Build onedir first (faster for testing)
    build(one_file=False, suffix="")

    # Build portable onefile
    build(one_file=True, suffix="-Portable")

    print("\n" + "-" * 40)
    print("[OK] All builds complete. Output in: " + DIST_DIR)
    print("  * dist/FileTransformer/              (folder bundle)")
    print("  * dist/FileTransformer-Portable.exe  (portable single file)")
    print("-" * 40 + "\n")


if __name__ == "__main__":
    main()
