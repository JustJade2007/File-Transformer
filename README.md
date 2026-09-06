# File-Transformer

A fully **local, privacy-focused** file conversion desktop application (and unified CLI) for Windows — no internet, no uploads, no subscriptions.

## Features

- 🔀 **80+ format conversions** across Audio, Video, Images, Documents, Data, Archives, Fonts, and Code
- 🖥️ **Modern desktop GUI** with drag-and-drop, conversion queue, and live progress bars
- ⚡ **Multi-threaded batch processing** — convert dozens of files in parallel
- 🎨 **3 selectable themes**: Cyber Dark, Minimalist Slate, Windows 11 Native
- ⚙️ **Smart presets + Advanced Options** per conversion (bitrate, quality, resolution, etc.)
- 📁 **Flexible output**: same-folder or custom output directory with auto-increment on collision
- 🎬 **FFmpeg auto-detection + 1-click portable download** for audio/video conversions
- 💻 **Unified CLI** — headless scripting mode via `python main.py -i <file> -f <format>`
- 📦 **Standalone `.exe`** — runs without any Python installation (via PyInstaller)

---

## Supported Formats

| Category   | Input Formats                                                  | Outputs                                               |
|------------|----------------------------------------------------------------|-------------------------------------------------------|
| **Audio**  | MP3, WAV, FLAC, AAC, OGG, M4A, WMA, AIFF, MIDI               | MP3, WAV, FLAC, AAC, OGG, M4A, WMA, AIFF, MP4, WEBM  |
| **Video**  | MP4, MKV, MOV, WEBM, AVI, WMV, FLV, M4V                      | MP4, MKV, MOV, WEBM, AVI, GIF, all audio formats     |
| **Images** | PNG, JPG, WEBP, BMP, ICO, TIFF, GIF, PSD, EPS                | PNG, JPG, WEBP, BMP, ICO, TIFF, GIF, PDF             |
| **Documents** | PDF, DOCX, TXT, MD, HTML, RTF, ODT, EPUB                  | TXT, PDF, DOCX, HTML, MD, PNG                        |
| **Data**   | CSV, TSV, JSON, XML, YAML, XLSX, SQLite, SQL                  | CSV, TSV, JSON, XML, YAML, XLSX, SQL, SQLite         |
| **Archives** | ZIP, TAR, GZ, BZ2, APK, JAR, DEB                           | ZIP, TAR, TAR.GZ, TAR.BZ2, GZ, BZ2                  |
| **Fonts**  | TTF, OTF, WOFF, WOFF2                                         | TTF, OTF, WOFF, WOFF2                                |
| **Code**   | PY, JS, TS, JAVA, C, CPP, CS, GO, RS, SH, BAT, PS1, etc.    | HTML, Markdown, PDF, TXT                             |

---

## Quick Start

### Run from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Launch GUI
python main.py

# CLI mode
python main.py -i video.mp4 -f mp3
python main.py -i *.png -f webp -o ./output
python main.py -i report.docx -f pdf
python main.py -i data.csv -f json --threads 4
```

### CLI Reference

```
python main.py -i <file_or_glob> -f <format> [options]

Options:
  -i, --input       Input file path or glob (e.g. *.png, folder/*.mp4)
  -f, --format      Target format extension (e.g. mp3, jpg, pdf)
  -o, --output      Output directory (default: same as source)
  --quality         Quality 1-100 for images/audio
  --bitrate         Audio/video bitrate (e.g. 192k, 5M)
  --threads N       Parallel worker count (default: 4)
  --overwrite       Overwrite existing files
```

---

## Build Executable (.exe)

```bash
python build.py
```

Produces:
- `dist/FileTransformer/` — fast-launch folder bundle
- `dist/FileTransformer-Portable.exe` — single portable file

---

## FFmpeg Setup

File-Transformer uses **FFmpeg** for all audio and video conversions. It is **not included** in the base package.

**Options:**
1. **In-app download** — Go to Settings → FFmpeg Engine → *Download Portable FFmpeg* (automatic, 1-click)
2. **System FFmpeg** — Install FFmpeg system-wide; the app will detect it automatically
3. **Custom path** — Specify a custom FFmpeg directory in Settings

> Image, Document, Data, Font, and Archive conversions work **without FFmpeg**.

---

## Project Structure

```
File-Transformer/
├── main.py          # Unified GUI/CLI entrypoint
├── cli.py           # Headless CLI runner
├── build.py         # PyInstaller build script
├── requirements.txt # Python dependencies
├── core/
│   ├── registry.py          # Format routing registry
│   ├── engine.py            # Multi-threaded conversion engine
│   ├── ffmpeg_manager.py    # FFmpeg detection & download
│   └── converters/
│       ├── base.py, media.py, images.py, documents.py
│       ├── data.py, archives.py, fonts.py, code.py
├── gui/
│   ├── app.py        # Main window & navigation
│   ├── theme.py      # Theme system (3 themes)
│   └── views/
│       ├── queue_view.py     # Conversion queue & drag-drop
│       ├── settings_view.py  # Settings & FFmpeg panel
│       └── about_view.py     # Format matrix & info
└── README.md
```

---

## Privacy

All conversions happen **100% locally on your machine**. No files are uploaded. No telemetry. No network requests (except the optional FFmpeg download).
