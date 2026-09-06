# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0.0] - 2026-09-06

### Added

#### Core Engine
- `core/registry.py` — Format routing registry mapping 84+ extensions across 7 categories to their converter
- `core/engine.py` — Multi-threaded ConversionEngine with ThreadPoolExecutor, per-task progress callbacks, and cancellation support
- `core/ffmpeg_manager.py` — Singleton FFmpeg manager with auto-detection (system PATH, local bin/), and 1-click portable static binary downloader

#### Converters
- `core/converters/base.py` — Abstract `BaseConverter` interface and `ConversionResult` dataclass
- `core/converters/media.py` — Audio/Video engine via FFmpeg (MP3, WAV, FLAC, AAC, OGG, M4A, WMA, AIFF, MP4, MKV, MOV, WEBM, AVI, WMV, FLV, GIF extraction, Audio→Video)
- `core/converters/images.py` — Raster image engine via Pillow (PNG, JPG, WEBP, BMP, ICO, TIFF, GIF, PDF, PSD)
- `core/converters/documents.py` — Document engine via PyPDF & python-docx (PDF, DOCX, TXT, MD, HTML, RTF, ODT, EPUB)
- `core/converters/data.py` — Serialization engine via openpyxl/pyyaml (CSV, TSV, JSON, XML, YAML, XLSX, SQLite, SQL)
- `core/converters/archives.py` — Archive engine (ZIP, TAR, GZ, BZ2, APK, JAR, DEB)
- `core/converters/fonts.py` — Font engine via FontTools (TTF, OTF, WOFF, WOFF2)
- `core/converters/code.py` — Code export engine (PY/JS/TS/Java/C/C++/C#/Go/Rust etc. → HTML, MD, PDF, TXT)

#### GUI
- `gui/theme.py` — Three-theme system (Cyber Dark, Minimalist Slate, Windows 11 Native) with JSON persistence
- `gui/app.py` — Main CTk window with sidebar navigation, first-launch theme welcome dialog, and view routing
- `gui/views/queue_view.py` — Drag-and-drop conversion queue with per-row format selectors, advanced options modal, live progress bars, and output folder control
- `gui/views/settings_view.py` — Settings panel: theme card picker, concurrency slider, default output dir, FFmpeg download card
- `gui/views/about_view.py` — Full supported format conversion matrix and app info

#### CLI & Build
- `cli.py` — Headless argparse CLI with glob input, parallel workers, live progress bar, and summary report
- `main.py` — Unified entrypoint (no args = GUI, args present = CLI)
- `build.py` — Automated PyInstaller script producing both onedir bundle and portable single-file `.exe`
- `requirements.txt` — Pinned Python dependencies

## [1.0.0.0] - 2026-04-05

### Added
- Initial project repository creation
- README.md outlining the core concept of a fully local file transformation app
- CHANGELOG.md established following custom versioning format (1.A.b.2)
