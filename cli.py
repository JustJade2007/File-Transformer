"""
CLI runner — headless conversion mode for File-Transformer.
Usage: FileTransformer.exe -i <path_or_glob> -f <format> [-o <output_dir>] [options]
"""
import argparse
import glob
import os
import sys
import threading
import time
from typing import List


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="File-Transformer",
        description="Local File Transformer — Convert files between formats, fully offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  File-Transformer -i video.mp4 -f mp3
  File-Transformer -i *.png -f webp -o ./output
  File-Transformer -i report.docx -f pdf --quality 95
  File-Transformer -i data.csv -f json --threads 2
""",
    )
    p.add_argument("-i", "--input", required=True, metavar="FILE_OR_GLOB",
                   help="Input file path or glob pattern (e.g. *.png, folder/*.mp4)")
    p.add_argument("-f", "--format", required=True, metavar="FORMAT",
                   help="Target output format extension (e.g. mp3, jpg, pdf)")
    p.add_argument("-o", "--output", metavar="OUTPUT_DIR", default=None,
                   help="Output directory (default: same folder as source)")
    p.add_argument("--quality", type=int, default=None, metavar="QUALITY",
                   help="Output quality (1-100) for image/audio conversions")
    p.add_argument("--bitrate", default=None, metavar="BITRATE",
                   help="Audio/video bitrate (e.g. 192k, 5M)")
    p.add_argument("--threads", type=int, default=4, metavar="N",
                   help="Number of parallel worker threads (default: 4)")
    p.add_argument("--overwrite", action="store_true",
                   help="Overwrite existing output files instead of auto-incrementing")
    return p


def run_cli(args: List[str] = None):
    parser = build_parser()
    parsed = parser.parse_args(args)

    # Resolve input files
    raw_input = parsed.input
    if os.path.isfile(raw_input):
        input_files = [raw_input]
    elif os.path.isdir(raw_input):
        input_files = []
        for root, _, fnames in os.walk(raw_input):
            for fname in fnames:
                input_files.append(os.path.join(root, fname))
    else:
        input_files = glob.glob(raw_input, recursive=True)

    if not input_files:
        print(f"[ERROR] No files found matching: {raw_input}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  File Transformer CLI")
    print(f"  ─────────────────────────────────────────")
    print(f"  Files   : {len(input_files)}")
    print(f"  Target  : .{parsed.format.lstrip('.')}")
    print(f"  Output  : {parsed.output or 'Same as source'}")
    print(f"  Threads : {parsed.threads}")
    print(f"  ─────────────────────────────────────────\n")

    # Build options
    options = {}
    if parsed.quality is not None:
        options["quality"] = parsed.quality
    if parsed.bitrate is not None:
        options["audio_bitrate"] = parsed.bitrate
        options["video_bitrate"] = parsed.bitrate

    # Bootstrap engine
    from core.engine import ConversionEngine, ConversionTask, TaskStatus, safe_output_path
    import uuid

    engine = ConversionEngine(max_workers=parsed.threads)

    # Track results
    results = {}
    lock = threading.Lock()
    all_done = threading.Event()
    task_ids = set()

    def on_complete(task_id, result):
        with lock:
            results[task_id] = result
            if len(results) == len(task_ids):
                all_done.set()

    def on_progress(task_id, frac, text):
        pass  # Progress handled inline via polling

    tasks = []
    for fpath in input_files:
        src_ext = os.path.splitext(fpath)[1].lower().lstrip(".")
        target_fmt = parsed.format.lstrip(".")

        output_path = safe_output_path(fpath, target_fmt, parsed.output)
        if parsed.overwrite and os.path.exists(output_path):
            os.remove(output_path)

        task = ConversionTask(
            task_id=str(uuid.uuid4()),
            source_path=fpath,
            target_format=target_fmt,
            output_dir=parsed.output,
            options=options,
        )
        tasks.append(task)
        task_ids.add(task.task_id)
        engine.submit(task, on_progress=on_progress, on_complete=on_complete)

    # Poll progress
    print("  Converting...")
    start_time = time.time()
    width = 40

    while not all_done.is_set():
        with lock:
            done_count = sum(
                1 for t in tasks
                if t.status.name in ("DONE", "ERROR", "CANCELLED")
            )

        pct = done_count / max(len(tasks), 1)
        filled = int(width * pct)
        bar = "█" * filled + "░" * (width - filled)
        elapsed = time.time() - start_time
        print(f"\r  [{bar}] {done_count}/{len(tasks)} ({elapsed:.1f}s)", end="", flush=True)

        if done_count >= len(tasks):
            break
        time.sleep(0.2)

    elapsed = time.time() - start_time
    print()  # newline after progress bar

    # Summary
    success_count = sum(1 for r in results.values() if r.success)
    error_count = len(results) - success_count

    print(f"\n  ─────────────────────────────────────────")
    print(f"  ✓ {success_count} succeeded   ✗ {error_count} failed   ({elapsed:.2f}s total)")
    print(f"  ─────────────────────────────────────────")

    for task in tasks:
        result = results.get(task.task_id)
        fname = os.path.basename(task.source_path)
        if result and result.success:
            out_name = os.path.basename(result.output_path or task.output_path or "")
            print(f"  ✓  {fname} → {out_name}")
        elif result:
            print(f"  ✗  {fname}: {result.error_message}")
        else:
            print(f"  ?  {fname}: no result")

    print()
    engine.shutdown(wait=False)
    return 0 if error_count == 0 else 1
