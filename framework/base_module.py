"""The common contract for all FC Hub modules."""

from framework.module_info import ModuleInfo


class BaseModule:
    module_info = None

    def __init__(self, **metadata):
        if metadata:
            self.module_info = ModuleInfo(**metadata)

    @property
    def info(self):
        """Compatibility alias used by the pre-framework UI."""
        return self.module_info

    def create_window(self, master):
        raise NotImplementedError("Module must implement create_window().")

