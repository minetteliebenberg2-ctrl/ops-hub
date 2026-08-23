"""Metadata shared by every FC Hub module."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleInfo:
    module_id: str
    name: str
    description: str
    category: str = "General"
    sort_order: int = 100
    enabled: bool = True
    visible: bool = True
    icon: str = ""
    version: str = "1.0"
    beta: bool = False

