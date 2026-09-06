"""
Conversion engine: thread-pool based batch worker with per-task progress,
cancellation support, and safe output path generation.
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional

from .registry import FormatRegistry
from .converters.base import ConversionResult


class TaskStatus(Enum):
    QUEUED = auto()
    CONVERTING = auto()
    DONE = auto()
    ERROR = auto()
    CANCELLED = auto()


@dataclass
class ConversionTask:
    """Represents a single file conversion job in the queue."""
    task_id: str
    source_path: str
    target_format: str
    output_dir: Optional[str] = None     # None = same dir as source
    options: Dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.QUEUED
    progress: float = 0.0
    status_text: str = "Queued"
    result: Optional[ConversionResult] = None
    output_path: Optional[str] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

    # Callbacks wired by engine
    on_progress: Optional[Callable] = field(default=None, repr=False)
    on_complete: Optional[Callable] = field(default=None, repr=False)


def safe_output_path(source_path: str, target_format: str, output_dir: Optional[str]) -> str:
    """
    Build a collision-safe output file path.
    If a file already exists, append _1, _2, etc. until the name is unique.
    """
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    ext = target_format.lower().lstrip(".")
    dest_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(source_path))
    os.makedirs(dest_dir, exist_ok=True)

    candidate = os.path.join(dest_dir, f"{base_name}.{ext}")
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{base_name}_{counter}.{ext}")
        counter += 1
    return candidate


class ConversionEngine:
    """
    Multi-threaded conversion engine managing a queue of ConversionTask objects.
    Supports parallel execution, per-task progress callbacks, and cancellation.
    """

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._registry = FormatRegistry()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures: Dict[str, Future] = {}
        self._tasks: Dict[str, ConversionTask] = {}
        self._lock = threading.Lock()
        self._global_cancel = threading.Event()

    def set_max_workers(self, n: int):
        self._max_workers = max(1, n)

    def submit(
        self,
        task: ConversionTask,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
        on_complete: Optional[Callable[[str, ConversionResult], None]] = None,
    ) -> str:
        """Add a task to the queue and start execution immediately."""
        task.on_progress = on_progress
        task.on_complete = on_complete

        with self._lock:
            self._tasks[task.task_id] = task

        if self._executor is None or self._executor._shutdown:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        future = self._executor.submit(self._run_task, task)
        with self._lock:
            self._futures[task.task_id] = future
        return task.task_id

    def cancel_task(self, task_id: str):
        """Signal a specific task to cancel."""
        with self._lock:
            task = self._tasks.get(task_id)
        if task:
            task.cancel_event.set()
            task.status = TaskStatus.CANCELLED
            task.status_text = "Cancelled"

    def cancel_all(self):
        """Cancel all active tasks."""
        with self._lock:
            ids = list(self._tasks.keys())
        for tid in ids:
            self.cancel_task(tid)

    def get_task(self, task_id: str) -> Optional[ConversionTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def all_tasks(self) -> List[ConversionTask]:
        with self._lock:
            return list(self._tasks.values())

    def clear_completed(self):
        """Remove all DONE, ERROR, and CANCELLED tasks from the internal map."""
        with self._lock:
            done_ids = [
                tid for tid, t in self._tasks.items()
                if t.status in (TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.CANCELLED)
            ]
            for tid in done_ids:
                self._tasks.pop(tid, None)
                self._futures.pop(tid, None)

    def shutdown(self, wait: bool = True):
        if self._executor:
            self._executor.shutdown(wait=wait, cancel_futures=not wait)

    def _run_task(self, task: ConversionTask):
        """Worker function executed in thread pool."""
        source_ext = os.path.splitext(task.source_path)[1].lower().lstrip(".")
        converter = self._registry.find_converter(source_ext, task.target_format)

        if not converter:
            task.status = TaskStatus.ERROR
            task.status_text = f"No converter found for .{source_ext} → .{task.target_format}"
            task.result = ConversionResult(
                success=False,
                error_message=task.status_text,
            )
            if task.on_complete:
                task.on_complete(task.task_id, task.result)
            return

        task.status = TaskStatus.CONVERTING
        task.status_text = "Converting..."

        output_path = safe_output_path(task.source_path, task.target_format, task.output_dir)
        task.output_path = output_path

        def progress_cb(frac: float, text: str):
            task.progress = frac
            task.status_text = text
            if task.on_progress:
                task.on_progress(task.task_id, frac, text)

        try:
            result = converter.convert(
                source_path=task.source_path,
                target_path=output_path,
                target_format=task.target_format,
                options=task.options if task.options else None,
                progress_callback=progress_cb,
                cancel_event=task.cancel_event,
            )

            task.result = result
            if result.success:
                task.status = TaskStatus.DONE
                task.status_text = "Done"
                task.progress = 1.0
                task.output_path = result.output_path or output_path
            elif task.cancel_event.is_set():
                task.status = TaskStatus.CANCELLED
                task.status_text = "Cancelled"
            else:
                task.status = TaskStatus.ERROR
                task.status_text = f"Error: {result.error_message or 'Unknown'}"

        except Exception as e:
            task.status = TaskStatus.ERROR
            task.status_text = f"Exception: {str(e)}"
            task.result = ConversionResult(success=False, error_message=str(e))

        if task.on_complete:
            task.on_complete(task.task_id, task.result)
