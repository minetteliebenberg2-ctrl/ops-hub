"""Native FC Hub Duplicate Finder window."""

from pathlib import Path
import queue
import threading
from tkinter import TclError, filedialog, messagebox, ttk

import customtkinter as ctk

from modules.duplicate_finder.services import (
    DuplicateFinderError,
    DuplicateRow,
    ScanProgress,
    ScanResult,
    delete_selected,
    export_report,
    format_size,
    scan_folder,
    sort_duplicate_rows,
)


class DuplicateFinderWindow(ctk.CTkFrame):
    """Responsive Treeview UI; scanning runs away from the Tk event loop."""

    columns = ("group", "original", "duplicate", "size", "hash")

    def __init__(self, master):
        super().__init__(master)
        self.selected_folder: Path | None = None
        self.result: ScanResult | None = None
        self._rows_by_item: dict[str, DuplicateRow] = {}
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cancel_event: threading.Event | None = None
        self._poll_after: str | None = None
        self._sort_reverse: dict[str, bool] = {}
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Duplicate Finder", font=("Segoe UI", 22, "bold")).pack(pady=(18, 5))
        ctk.CTkLabel(self, text="Find content-identical files and safely move selected copies to the Recycle Bin.").pack(pady=(0, 12))

        folder_row = ctk.CTkFrame(self)
        folder_row.pack(fill="x", padx=15, pady=5)
        self.choose_button = ctk.CTkButton(folder_row, text="Choose Folder", command=self.choose_folder, width=130)
        self.choose_button.pack(side="left", padx=5, pady=8)
        self.folder_label = ctk.CTkLabel(folder_row, text="No folder selected", anchor="w")
        self.folder_label.pack(side="left", fill="x", expand=True, padx=8)

        self.stats_label = ctk.CTkLabel(self, text="Scanned: 0 | Unique: 0 | Duplicate groups: 0 | Recoverable: 0 B", anchor="w")
        self.stats_label.pack(fill="x", padx=20, pady=(4, 5))
        self.progress_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.progress_label.pack(fill="x", padx=20, pady=(0, 5))
        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.pack(fill="x", padx=20, pady=(0, 8))

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=5)
        self.results_table = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="extended", height=15)
        headings = {"group": "Group", "original": "Retained Copy", "duplicate": "Duplicate Copy", "size": "Size", "hash": "SHA-256"}
        widths = {"group": 90, "original": 300, "duplicate": 300, "size": 100, "hash": 380}
        for column in self.columns:
            self.results_table.heading(column, text=headings[column], command=lambda value=column: self.sort_results(value))
            self.results_table.column(column, width=widths[column], minwidth=80, anchor="w", stretch=column in {"duplicate", "hash"})
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.results_table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.results_table.xview)
        self.results_table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.results_table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=5)
        self.scan_button = ctk.CTkButton(button_row, text="Find Duplicates", command=self.start_scan, width=130)
        self.scan_button.pack(side="left", padx=5, pady=8)
        self.cancel_button = ctk.CTkButton(button_row, text="Cancel Scan", command=self.cancel_scan, width=110, state="disabled")
        self.cancel_button.pack(side="left", padx=5, pady=8)
        self.delete_button = ctk.CTkButton(button_row, text="Move Selected to Recycle Bin", command=self.delete_selected, width=210, state="disabled")
        self.delete_button.pack(side="left", padx=5, pady=8)
        self.export_button = ctk.CTkButton(button_row, text="Export Results", command=self.export_results, width=130, state="disabled")
        self.export_button.pack(side="left", padx=5, pady=8)
        self.reset_button = ctk.CTkButton(button_row, text="Reset", command=self.reset, width=90)
        self.reset_button.pack(side="left", padx=5, pady=8)
        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.pack(fill="x", padx=20, pady=(3, 12))

    def choose_folder(self):
        if self._is_scanning():
            return
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), title="Choose Folder to Scan")
        if not folder:
            return
        self.selected_folder = Path(folder).expanduser().resolve()
        self.folder_label.configure(text=str(self.selected_folder))
        self.reset_results("Folder selected; ready to scan.")

    def start_scan(self):
        if self._is_scanning():
            return
        if not self.selected_folder or not self.selected_folder.is_dir():
            messagebox.showwarning("Duplicate Finder", "Choose a valid folder before scanning.", parent=self.winfo_toplevel())
            return
        self.reset_results("Scanning started.")
        self._cancel_event = threading.Event()
        self._worker = threading.Thread(target=self._scan_worker, args=(self.selected_folder, self._cancel_event), daemon=True)
        self._set_scanning(True)
        self._worker.start()
        self._poll_after = self.after(50, self._poll_worker)

    def _scan_worker(self, folder: Path, cancel_event: threading.Event):
        try:
            result = scan_folder(folder, cancel_event=cancel_event, progress_callback=lambda progress: self._queue.put(("progress", progress)))
            self._queue.put(("done", result))
        except Exception as error:
            self._queue.put(("error", error))

    def _poll_worker(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "progress":
                    progress = payload
                    self.progress_label.configure(text=f"Scanning {progress.scanned_files} file(s): {progress.current_path}")
                elif kind == "done":
                    self._finish_scan(payload)
                elif kind == "error":
                    self._set_scanning(False)
                    messagebox.showerror("Duplicate Finder", str(payload), parent=self.winfo_toplevel())
                    self.status_label.configure(text="Scan failed; no files were changed.")
        except queue.Empty:
            pass
        if self._worker and not self._worker.is_alive():
            self._set_scanning(False)
        if self._is_scanning() or not self._queue.empty():
            self._poll_after = self.after(50, self._poll_worker)

    def _finish_scan(self, result: ScanResult):
        self.result = result
        self._set_scanning(False)
        self._insert_rows(result.rows())
        self._update_statistics()
        if result.cancelled:
            self.status_label.configure(text="Scan cancelled; partial results were discarded.")
        elif result.issues:
            self.status_label.configure(text=f"Scan complete with {len(result.issues)} skipped/unreadable item(s). Review the status details.")
        else:
            self.status_label.configure(text="Scan complete.")
        self.progress_label.configure(text=f"Elapsed: {result.elapsed_seconds:.2f} second(s)")

    def cancel_scan(self):
        if self._cancel_event:
            self._cancel_event.set()
            self.status_label.configure(text="Cancelling scan…")

    def delete_selected(self):
        if not self.result:
            return
        selected = self.results_table.selection()
        if not selected:
            messagebox.showwarning("Delete", "Select one or more duplicate copies.", parent=self.winfo_toplevel())
            return
        paths = [self._rows_by_item[item].duplicate.path for item in selected]
        if not messagebox.askyesno(
            "Confirm Recycle Bin Move",
            f"Move {len(paths)} selected duplicate copy/copies to the Recycle Bin?\n\nThe retained copy in each group will be protected.",
            parent=self.winfo_toplevel(),
        ):
            return
        result = delete_selected(self.result.groups, paths, confirmed=True, scan_result=self.result)
        if result.remaining_result:
            self.result = result.remaining_result
            self._insert_rows(self.result.rows())
            self._update_statistics()
        if result.failures:
            details = "\n".join(f"{failure.path}: {failure.reason}" for failure in result.failures)
            messagebox.showwarning("Recycle Bin Move", result.message + "\n\n" + details, parent=self.winfo_toplevel())
        elif result.deleted_paths:
            messagebox.showinfo("Recycle Bin Move", result.message, parent=self.winfo_toplevel())
        self.status_label.configure(text=result.message)

    def export_results(self):
        if not self.result or not self.result.groups:
            messagebox.showwarning("Export", "There are no duplicate results to export.", parent=self.winfo_toplevel())
            return
        filename = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Duplicate_Report.csv",
        )
        if not filename:
            return
        try:
            export_report(self.result, filename)
        except (OSError, DuplicateFinderError) as error:
            messagebox.showerror("Export", str(error), parent=self.winfo_toplevel())
            return
        messagebox.showinfo("Export", "Duplicate report exported successfully.", parent=self.winfo_toplevel())
        self.status_label.configure(text=f"Report exported to {filename}")

    def sort_results(self, column: str):
        if not self.result:
            return
        reverse = not self._sort_reverse.get(column, False)
        self._sort_reverse[column] = reverse
        selected_paths = {_normalise_row_path(row.duplicate.path) for item, row in self._rows_by_item.items() if item in self.results_table.selection()}
        rows = sort_duplicate_rows(self.result.rows(), column, reverse)
        self._insert_rows(rows, selected_paths)

    def reset(self):
        self.cancel_scan()
        self.selected_folder = None
        self.folder_label.configure(text="No folder selected")
        self.reset_results("Ready")

    def reset_results(self, status: str):
        self.result = None
        self._rows_by_item.clear()
        self.results_table.delete(*self.results_table.get_children())
        self.stats_label.configure(text="Scanned: 0 | Unique: 0 | Duplicate groups: 0 | Recoverable: 0 B")
        self.progress_label.configure(text="Ready")
        self.status_label.configure(text=status)
        self._set_result_buttons(False)

    def _insert_rows(self, rows, selected_paths: set[Path] | None = None):
        self.results_table.delete(*self.results_table.get_children())
        self._rows_by_item.clear()
        selected_paths = selected_paths or set()
        for index, row in enumerate(rows):
            item_id = f"row_{index}"
            self._rows_by_item[item_id] = row
            self.results_table.insert(
                "",
                "end",
                iid=item_id,
                values=(row.group_id, str(row.original.path), str(row.duplicate.path), format_size(row.size), row.sha256),
            )
            if _normalise_row_path(row.duplicate.path) in selected_paths:
                self.results_table.selection_add(item_id)

    def _update_statistics(self):
        if not self.result:
            return
        self.stats_label.configure(
            text=(
                f"Scanned: {self.result.files_scanned} | Unique: {self.result.unique_files} | "
                f"Duplicate groups: {self.result.duplicate_group_count} | Redundant copies: {self.result.duplicate_file_count} | "
                f"Recoverable: {format_size(self.result.recoverable_bytes)} | Skipped: {self.result.skipped_files}"
            )
        )
        self._set_result_buttons(bool(self.result.groups))

    def _set_scanning(self, scanning: bool):
        self.choose_button.configure(state="disabled" if scanning else "normal")
        self.scan_button.configure(state="disabled" if scanning else "normal")
        self.cancel_button.configure(state="normal" if scanning else "disabled")
        self.reset_button.configure(state="disabled" if scanning else "normal")
        if scanning:
            self.progress.start(10)
        else:
            self.progress.stop()
            self._set_result_buttons(bool(self.result and self.result.groups))

    def _set_result_buttons(self, enabled: bool):
        state = "normal" if enabled and not self._is_scanning() else "disabled"
        self.delete_button.configure(state=state)
        self.export_button.configure(state=state)

    def _is_scanning(self) -> bool:
        return bool(self._worker and self._worker.is_alive())

    def destroy(self):
        if self._cancel_event:
            self._cancel_event.set()
        if self._poll_after:
            try:
                self.after_cancel(self._poll_after)
            except (RuntimeError, TclError):
                pass
        super().destroy()


def _normalise_row_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


__all__ = ["DuplicateFinderWindow"]
