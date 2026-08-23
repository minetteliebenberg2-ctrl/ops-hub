"""Safe diagnostic execution independent of the GUI."""

import logging
from dataclasses import replace
from time import perf_counter

from core.diagnostics.models import DiagnosticResult, DiagnosticStatus


LOGGER = logging.getLogger(__name__)


class DiagnosticRunner:
    def __init__(self, registry):
        self.registry = registry

    def run_all(self):
        return self._run(self.registry.get_checks())

    def run_selected(self, check_ids):
        checks = []
        for check_id in check_ids:
            check = self.registry.get(check_id)
            if check is None:
                checks.append(_UnknownCheck(check_id))
            else:
                checks.append(check)
        return self._run(checks)

    def _run(self, checks):
        LOGGER.info("Starting FC Hub diagnostic run")
        results = []
        for check in checks:
            started = perf_counter()
            try:
                produced = check.run()
                items = produced if isinstance(produced, (list, tuple)) else [produced]
                for item in items:
                    if not isinstance(item, DiagnosticResult):
                        raise TypeError("Diagnostic checks must return DiagnosticResult values.")
                    results.append(replace(item, duration_seconds=perf_counter() - started))
            except Exception as error:
                LOGGER.exception("Diagnostic check %s failed unexpectedly", check.check_id)
                results.append(DiagnosticResult(
                    check_id=check.check_id,
                    category=getattr(check, "category", "Diagnostics"),
                    name=getattr(check, "name", check.check_id),
                    status=DiagnosticStatus.FAIL,
                    summary="The check could not be completed.",
                    details=f"{type(error).__name__}: {error}",
                    recommendation="Review the details and application log, then retry the check.",
                    is_blocking=True,
                    duration_seconds=perf_counter() - started,
                ))
        LOGGER.info("Completed FC Hub diagnostic run: %s result(s)", len(results))
        return results


class _UnknownCheck:
    category = "Diagnostics"
    name = "Unknown selected check"

    def __init__(self, check_id):
        self.check_id = check_id

    def run(self):
        return DiagnosticResult(
            self.check_id, self.category, self.name, DiagnosticStatus.FAIL,
            "The selected check is not registered.",
            f"No registered diagnostic has ID '{self.check_id}'.",
            "Refresh the result list and select a registered check.", True,
        )
