"""Registration and discovery for independent diagnostic checks."""


class DiagnosticRegistry:
    def __init__(self):
        self._checks = {}

    def register(self, check):
        check_id = getattr(check, "check_id", "")
        if not check_id:
            raise ValueError("A diagnostic check requires a stable check_id.")
        if check_id in self._checks:
            raise ValueError(f"Duplicate diagnostic check ID: {check_id}")
        self._checks[check_id] = check
        return check

    def get_checks(self):
        return list(self._checks.values())

    def get(self, check_id):
        return self._checks.get(check_id)

    def __len__(self):
        return len(self._checks)
