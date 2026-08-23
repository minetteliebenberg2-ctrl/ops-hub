"""Shared workspace host for FC Hub module windows."""

import customtkinter as ctk


class ModuleHost(ctk.CTkFrame):
    """Own the active module window and the common workspace margin."""

    WORKSPACE_PADDING = 20

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.active_frame = None

    def clear(self):
        """Destroy the active workspace exactly once."""
        active_frame = self.active_frame
        self.active_frame = None
        if active_frame is not None and active_frame.winfo_exists():
            active_frame.destroy()

    def mount(self, window_factory):
        """Replace the active workspace with a newly created module window."""
        self.clear()

        try:
            active_frame = window_factory(self)
            if active_frame is None or not hasattr(active_frame, "pack"):
                raise TypeError("create_window(master) must return a widget")
        except Exception as error:
            active_frame = self._create_error_frame(error)

        self.active_frame = active_frame
        active_frame.pack(
            fill="both",
            expand=True,
            padx=self.WORKSPACE_PADDING,
            pady=self.WORKSPACE_PADDING,
        )
        self.after_idle(lambda frame=active_frame: self._focus(frame))
        return active_frame

    def show_home(self):
        """Mount the standard home view through the same workspace path."""
        def create_home(master):
            frame = ctk.CTkFrame(master)
            ctk.CTkLabel(
                frame,
                text="Select a module from the left menu to begin.",
                font=("Segoe UI", 18),
            ).pack(expand=True, pady=80)
            return frame

        return self.mount(create_home)

    @staticmethod
    def _focus(frame):
        if frame.winfo_exists():
            frame.focus_set()

    def _create_error_frame(self, error):
        import traceback, pathlib
        log = pathlib.Path(__file__).parent.parent / "module_error.log"
        try:
            with open(log, "a") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        frame = ctk.CTkFrame(self)
        ctk.CTkLabel(
            frame,
            text=f"Unable to open this module.\n{error}",
            font=("Segoe UI", 16),
            justify="center",
        ).pack(expand=True, padx=30, pady=30)
        return frame
