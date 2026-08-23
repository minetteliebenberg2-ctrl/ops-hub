"""Structured diagnostic result types."""

from dataclasses import dataclass
from enum import Enum


class DiagnosticStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INFO = "INFO"


@dataclass(frozen=True)
class DiagnosticResult:
    check_id: str
    category: str
    name: str
    status: DiagnosticStatus
    summary: str
    details: str
    recommendation: str
    is_blocking: bool = False
    duration_seconds: float = 0.0

    def __post_init__(self):
        if not all((self.check_id, self.category, self.name, self.summary)):
            raise ValueError("Diagnostic result required fields cannot be blank.")
        if not isinstance(self.status, DiagnosticStatus):
            raise ValueError("status must be a DiagnosticStatus value.")
