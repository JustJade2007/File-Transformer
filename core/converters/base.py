"""Base converter definitions and interface for File-Transformer."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import os
import time
from typing import Callable, Dict, List, Optional, Set


@dataclass
class ConversionResult:
    """Represents the outcome of a single file conversion."""
    success: bool
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    details: Dict = field(default_factory=dict)


class BaseConverter(ABC):
    """Abstract base class that all format-specific converters must implement."""

    name: str = "BaseConverter"
    category: str = "General"

    @abstractmethod
    def supported_inputs(self) -> Set[str]:
        """Return a set of supported input extensions (lowercase, without leading dot)."""
        pass

    @abstractmethod
    def supported_outputs(self, input_ext: Optional[str] = None) -> Set[str]:
        """Return a set of supported output extensions for a given input extension."""
        pass

    def can_convert(self, source_ext: str, target_ext: str) -> bool:
        """Check if this converter can handle the requested conversion pair."""
        source_clean = source_ext.lower().lstrip(".")
        target_clean = target_ext.lower().lstrip(".")
        return (source_clean in self.supported_inputs() and 
                target_clean in self.supported_outputs(source_clean))

    def get_default_options(self, source_ext: str, target_ext: str) -> Dict:
        """Return default conversion configuration options for UI/CLI customization."""
        return {}

    @abstractmethod
    def convert(
        self,
        source_path: str,
        target_path: str,
        target_format: str,
        options: Optional[Dict] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_event: Optional[object] = None,
    ) -> ConversionResult:
        """
        Execute the conversion.

        Args:
            source_path: Absolute path to the source file.
            target_path: Absolute destination path for the transformed file.
            target_format: Desired target file extension (lowercase, no dot).
            options: Optional configuration dictionary (e.g. quality, bitrate).
            progress_callback: Optional callback(fraction 0.0-1.0, status_text).
            cancel_event: Optional threading.Event to abort processing.

        Returns:
            ConversionResult instance.
        """
        pass
