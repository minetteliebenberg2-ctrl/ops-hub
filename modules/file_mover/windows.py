"""Native FC Hub File Mover window."""

from pathlib import Path
import queue
import threading
from tkinter import TclError, filedialog, messagebox, ttk

import customtkinter as ctk

from modules.file_mover.services import (
    FAILED,
    FileMovePreview,
    MoveBatchSummary,
    MoveProgress,
    MovePreview,
    build_preview,
    execute_move,
    export_csv,
)


class FileMoverWindow(ctk.CTkFrame):
    """Preview-driven File Mover UI with safe worker-thread coordination."""

    columns = ("source", "destination", "status")

    def __init__(self, master):
        super().__init__(master)
        self.source_folder: Path | None = None
        self.destination_folder: Path | None = None
        self.preview: MovePreview | None = None
        self._rows: dict[str, FileMovePreview] = {}
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cancel_event: threading.Event | None = None
        self._active = False
        self._poll_after: str | None = None
        self._build_ui()
        self._update_controls()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Bulk File Mover", font=("Segoe UI", 22, "bold")).pack(pady=(18, 5))
        ctk.CTkLabel(self, text="Preview a flattened move from one source folder to one destination folder.").pack(pady=(0, 12))

        source_row = ctk.CTkFrame(self)
        source_row.pack(fill="x", padx=15, pady=4)
        self.source_button = ctk.CTkButton(source_row, text="Choose Source Folder", command=self.choose_source, width=170)
        self.source_button.pack(side="left", padx=5, pady=8)
        self.source_label = ctk.CTkLabel(source_row, text="No source folder selected", anchor="w")
        self.source_label.pack(side="left", fill="x", expand=True, padx=8)

        destination_row = ctk.CTkFrame(self)
        destination_row.pack(fill="x", padx=15, pady=4)
        self.destination_button = ctk.CTkButton(destination_row, text="Choose Destination Folder", command=self.choose_destination, width=190)
        self.destination_button.pack(side="left", padx=5, pady=8)
        self.destination_label = ctk.CTkLabel(destination_row, text="No destination folder selected", anchor="w")
        self.destination_label.pack(side="left", fill="x", expand=True, padx=8)

        self.stats_label = ctk.CTkLabel(self, text="Files: 0", anchor="w")
        self.stats_label.pack(fill="x", padx=20, pady=(4, 3))
        self.progress_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.progress_label.pack(fill="x", padx=20, pady=(0, 4))
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=20, pady=(0, 8))

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.preview_table = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="extended", height=15)
        headings = {"source": "Source", "destination": "Destination", "status": "Status"}
        widths = {"source": 440, "destination": 440, "status": 110}
        for column in self.columns:
            self.preview_table.heading(column, text=headings[column])
            self.preview_table.column(column, width=widths[column], minwidth=90, anchor="w", stretch=column != "status")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.preview_table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.preview_table.xview)
        self.preview_table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.preview_table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=5)
        self.preview_button = ctk.CTkButton(button_row, text="Preview", command=self.start_preview, width=110)
        self.preview_button.pack(side="left", padx=5, pady=8)
        self.move_button = ctk.CTkButton(button_row, text="Move Files", command=self.confirm_and_move, width=110)
        self.move_button.pack(side="left", padx=5, pady=8)
        self.export_button = ctk.CTkButton(button_row, text="Export CSV", command=self.export_results, width=110)
        self.export_button.pack(side="left", padx=5, pady=8)
        self.cancel_button = ctk.CTkButton(button_row, text="Cancel", command=self.cancel_operation, width=95)
        self.cancel_button.pack(side="left", padx=5, pady=8)
        self.reset_button = ctk.CTkButton(button_row, text="Reset", command=self.reset, width=90)
        self.reset_button.pack(side="left", padx=5, pady=8)
        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.pack(fill="x", padx=20, pady=(3, 12))

    def choose_source(self):
        if self._active:
            return
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), title="Choose Source Folder")
        if folder:
            self.source_folder = Path(folder).expanduser().resolve()
            self.source_label.configure(text=str(self.source_folder))
            self._invalidate_preview("Source changed; build a new preview.")

    def choose_destination(self):
        if self._active:
            return
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), title="Choose Destination Folder")
        if folder:
            self.destination_folder = Path(folder).expanduser().resolve()
            self.destination_label.configure(text=str(self.destination_folder))
            self._invalidate_preview("Destination changed; build a new preview.")

    def start_preview(self):
        if self._active:
            return
        if not self.source_folder or not self.source_folder.is_dir():
            messagebox.showwarning("Source", "Choose a valid source folder.", parent=self.winfo_toplevel())
            return
        if not self.destination_folder or not self.destination_folder.is_dir():
            messagebox.showwarning("Destination", "Choose an existing destination folder.", parent=self.winfo_toplevel())
            return
        self._begin_operation("preview")
        self._worker = threading.Thread(target=self._preview_worker, args=(self.source_folder, self.destination_folder), daemon=True)
        self._worker.start()
        self._poll_after = self.after(50, self._poll_worker)

    def _preview_worker(self, source: Path, destination: Path):
        try:
            preview = build_preview(
                source,
                destination,
                cancel_event=self._cancel_event,
                progress_callback=lambda progress: self._queue.put(("progress", progress)),
            )
            self._queue.put(("preview_done", preview))
        except Exception as error:
            self._queue.put(("error", error))

    def confirm_and_move(self):
        if self._active or not self.preview or not self.preview.valid:
            messagebox.showwarning("Move", "Build a valid preview before moving files.", parent=self.winfo_toplevel())
            return
        pending = sum(entry.status == "Pending" for entry in self.preview.entries)
        if not pending:
            messagebox.showinfo("Move", "There are no Pending preview entries to move.", parent=self.winfo_toplevel())
            return
        message = (
            f"Preview entries: {pending}\n"
            f"Source folder:\n{self.preview.source_folder}\n\n"
            f"Destination folder:\n{self.preview.destination_folder}\n\n"
            "The destination structure will be flattened.\n"
            "Existing destination files will be skipped.\n"
            "Successfully moved files will be removed from the source.\n\n"
            "Continue?"
        )
        if not messagebox.askyesno("Confirm Move", message, parent=self.winfo_toplevel()):
            self.status_label.configure(text="Move cancelled; no files changed.")
            return
        self._begin_operation("move")
        self._worker = threading.Thread(target=self._move_worker, args=(self.preview,), daemon=True)
        self._worker.start()
        self._poll_after = self.after(50, self._poll_worker)

    def _move_worker(self, preview: MovePreview):
        try:
            summary = execute_move(
                preview,
                confirmed=True,
                cancel_event=self._cancel_event,
                progress_callback=lambda progress: self._queue.put(("progress", progress)),
            )
            self._queue.put(("move_done", summary))
        except Exception as error:
            self._queue.put(("error", error))

    def _poll_worker(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    self._show_progress(payload)
                elif kind == "preview_done":
                    self.preview = payload
                    self._render_preview()
                    self._end_operation()
                    if self.preview.cancelled:
                        self.status_label.configure(text="Preview cancelled; no files were moved.")
                    elif self.preview.blocking_issues:
                        messagebox.showwarning("Preview", "\n".join(self.preview.blocking_issues), parent=self.winfo_toplevel())
                        self.status_label.configure(text="Preview blocked; no files can be moved.")
                    elif self.preview.issues:
                        self.status_label.configure(text=f"Preview ready with {len(self.preview.issues)} scan warning(s).")
                    else:
                        self.status_label.configure(text="Preview ready; review it before moving files.")
                    self.progress_label.configure(text=f"Preview entries: {len(self.preview.entries)}")
                elif kind == "move_done":
                    self._render_preview()
                    self._end_operation()
                    self._show_completion(payload)
                elif kind == "error":
                    self._end_operation()
                    messagebox.showerror("File Mover", str(payload), parent=self.winfo_toplevel())
                    self.status_label.configure(text="Operation failed; review the preview and try again.")
        except queue.Empty:
            pass
        if self._active or not self._queue.empty():
            self._poll_after = self.after(50, self._poll_worker)

    def _show_progress(self, progress: MoveProgress):
        phase = "Scanning" if progress.phase == "preview" else "Moving"
        current = f": {progress.current_path}" if progress.current_path else ""
        if progress.total:
            text = f"{phase} {progress.processed}/{progress.total}{current}"
        else:
            text = f"{phase} {progress.processed} file(s){current}"
        self.progress_label.configure(text=text)
        if progress.phase == "preview":
            self.progress.configure(mode="indeterminate")
        if progress.phase == "move":
            self.progress.configure(mode="determinate", maximum=max(1, progress.total), value=progress.processed)

    def cancel_operation(self):
        if self._cancel_event:
            self._cancel_event.set()
            self.status_label.configure(text="Cancellation requested; the current file may finish.")

    def export_results(self):
        if not self.preview or not self.preview.entries:
            messagebox.showwarning("Export", "Build a preview before exporting results.", parent=self.winfo_toplevel())
            return
        filename = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Move_Report.csv",
        )
        if not filename:
            return
        try:
            export_csv(self.preview, filename)
        except OSError as error:
            messagebox.showerror("Export", str(error), parent=self.winfo_toplevel())
            return
        messagebox.showinfo("Export", "Report exported successfully.", parent=self.winfo_toplevel())
        self.status_label.configure(text=f"Report exported to {filename}")

    def reset(self):
        if self._active:
            return
        self.source_folder = None
        self.destination_folder = None
        self.source_label.configure(text="No source folder selected")
        self.destination_label.configure(text="No destination folder selected")
        self._invalidate_preview("Ready")

    def _invalidate_preview(self, status: str):
        self.preview = None
        self._rows.clear()
        self.preview_table.delete(*self.preview_table.get_children())
        self.stats_label.configure(text="Files: 0")
        self.progress_label.configure(text="Ready")
        self.status_label.configure(text=status)
        self._update_controls()

    def _render_preview(self):
        self.preview_table.delete(*self.preview_table.get_children())
        self._rows.clear()
        if not self.preview:
            self._update_controls()
            return
        for index, entry in enumerate(self.preview.entries):
            item_id = f"row_{index}"
            self._rows[item_id] = entry
            self.preview_table.insert("", "end", iid=item_id, values=(str(entry.source), str(entry.destination), entry.status))
        self.stats_label.configure(text=f"Files: {len(self.preview.entries)} | Pending: {sum(item.status == 'Pending' for item in self.preview.entries)}")
        self._update_controls()

    def _show_completion(self, summary: MoveBatchSummary):
        self.stats_label.configure(
            text=f"Files: {len(summary.entries)} | Moved: {summary.moved} | Skipped: {summary.skipped} | Failed: {summary.failed}"
        )
        self.progress_label.configure(text=f"Elapsed: {summary.elapsed:.2f} second(s)")
        self.status_label.configure(text="Move cancelled." if summary.cancelled else "Move complete.")
        lines = [
            f"Moved: {summary.moved}",
            f"Skipped: {summary.skipped}",
            f"Failed: {summary.failed}",
            f"Elapsed: {summary.elapsed:.2f} sec",
        ]
        failures = [f"{entry.source}: {entry.error}" for entry in summary.entries if entry.status == FAILED and entry.error]
        if summary.cancelled:
            lines.append("Cancellation was requested; unprocessed entries remain Pending.")
        if failures:
            lines.append("\nFailures:\n" + "\n".join(failures))
        dialog = messagebox.showwarning if summary.failed else messagebox.showinfo
        dialog("File Mover", "\n".join(lines), parent=self.winfo_toplevel())

    def _begin_operation(self, kind: str):
        self._active = True
        self._cancel_event = threading.Event()
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(10)
        self.progress_label.configure(text="Scanning..." if kind == "preview" else "Preparing move...")
        self._update_controls()

    def _end_operation(self):
        self._active = False
        self.progress.stop()
        self._update_controls()

    def _update_controls(self):
        if self._active:
            for button in (self.source_button, self.destination_button, self.preview_button, self.move_button, self.export_button, self.reset_button):
                button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            return
        self.source_button.configure(state="normal")
        self.destination_button.configure(state="normal")
        valid_folders = bool(self.source_folder and self.source_folder.is_dir() and self.destination_folder and self.destination_folder.is_dir())
        self.preview_button.configure(state="normal" if valid_folders else "disabled")
        has_preview = bool(self.preview and self.preview.entries)
        has_pending = bool(self.preview and self.preview.valid and any(entry.status == "Pending" for entry in self.preview.entries))
        self.move_button.configure(state="normal" if has_pending else "disabled")
        self.export_button.configure(state="normal" if has_preview else "disabled")
        self.cancel_button.configure(state="disabled")
        self.reset_button.configure(state="normal")

    def destroy(self):
        if self._cancel_event:
            self._cancel_event.set()
        if self._poll_after:
            try:
                self.after_cancel(self._poll_after)
            except (TclError, RuntimeError):
                pass
        super().destroy()


__all__ = ["FileMoverWindow"]
