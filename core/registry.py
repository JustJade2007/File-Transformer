"""
Format registry: maps file extensions to converter instances and valid target formats.
This is the central routing table for File-Transformer.
"""
from typing import Dict, List, Optional, Tuple

from .converters.base import BaseConverter
from .converters.media import MediaConverter
from .converters.images import ImageConverter
from .converters.documents import DocumentConverter
from .converters.data import DataConverter
from .converters.archives import ArchiveConverter
from .converters.fonts import FontConverter
from .converters.code import CodeConverter


class FormatRegistry:
    """Singleton registry that routes file extensions to their appropriate converter."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._built = False
        return cls._instance

    def __init__(self):
        if self._built:
            return
        self._converters: List[BaseConverter] = [
            MediaConverter(),
            ImageConverter(),
            DocumentConverter(),
            DataConverter(),
            ArchiveConverter(),
            FontConverter(),
            CodeConverter(),
        ]
        self._built = True

    def find_converter(self, source_ext: str, target_ext: str) -> Optional[BaseConverter]:
        """Return the first converter that can handle the source -> target pair."""
        for conv in self._converters:
            if conv.can_convert(source_ext, target_ext):
                return conv
        return None

    def get_valid_targets(self, source_ext: str) -> Dict[str, List[str]]:
        """
        Return a dict mapping category -> list of target extensions
        that are reachable from source_ext.
        """
        clean = source_ext.lower().lstrip(".")
        results: Dict[str, List[str]] = {}
        for conv in self._converters:
            if clean in conv.supported_inputs():
                targets = sorted(conv.supported_outputs(clean))
                if targets:
                    category = conv.category
                    results.setdefault(category, []).extend(targets)
        return results

    def get_all_supported_inputs(self) -> Dict[str, List[str]]:
        """Return a dict of category -> sorted list of all input extensions."""
        result: Dict[str, List[str]] = {}
        for conv in self._converters:
            exts = sorted(conv.supported_inputs())
            result.setdefault(conv.category, []).extend(exts)
        return result

    def all_converters(self) -> List[BaseConverter]:
        return list(self._converters)
