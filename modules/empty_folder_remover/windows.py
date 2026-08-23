"""Native FC Hub Empty Folder Remover window."""

from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from modules.empty_folder_remover.services import (
    EmptyFolderError,
    EmptyFolderService,
    ScanResult,
)


class EmptyFolderRemoverWindow(ctk.CTkFrame):
    """Legacy-compatible one-column Treeview UI backed by the native service."""

    def __init__(self, master):
        super().__init__(master)
        self.service = EmptyFolderService()
        self.selected_folder: Path | None = None
        self.result: ScanResult | None = None
        self._paths_by_item: dict[str, Path] = {}
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(
            self,
            text="Empty Folder Remover",
            font=("Segoe UI", 22, "bold"),
        ).pack(pady=(18, 20))

        ctk.CTkButton(
            self,
            text="Choose Folder",
            command=self.choose_folder,
        ).pack(pady=(0, 10))

        self.folder_label = ctk.CTkLabel(self, text="No folder selected")
        self.folder_label.pack(pady=(0, 10))

        self.stats_label = ctk.CTkLabel(
            self,
            text="Folders: 0 | Empty: 0 | Skipped: 0 | Elapsed: 0.00 sec",
        )
        self.stats_label.pack(pady=(0, 15))

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True)
        self.preview_table = ttk.Treeview(
            table_frame,
            columns=("Folder",),
            show="headings",
            selectmode="extended",
        )
        self.preview_table.heading("Folder", text="Empty Folder")
        self.preview_table.column("Folder", width=900, anchor="w")
        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.preview_table.yview,
        )
        self.preview_table.configure(yscrollcommand=scrollbar.set)
        self.preview_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", pady=15)
        ctk.CTkButton(
            button_frame,
            text="Find Empty Folders",
            command=self.find_folders,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            button_frame,
            text="Delete Selected",
            command=self.delete_selected,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            button_frame,
            text="Export CSV",
            command=self.export_results,
        ).pack(side="left", padx=5)

    def choose_folder(self):
        folder = filedialog.askdirectory(
            parent=self.winfo_toplevel(),
            title="Choose Folder",
        )
        if folder:
            self.selected_folder = Path(folder).expanduser().resolve()
            self.folder_label.configure(text=str(self.selected_folder))

    def find_folders(self):
        if not self.selected_folder:
            messagebox.showwarning(
                "Folder",
                "Please choose a folder.",
                parent=self.winfo_toplevel(),
            )
            return
        try:
            result = self.service.scan(self.selected_folder)
        except (EmptyFolderError, OSError) as error:
            messagebox.showerror(
                "Empty Folder Remover",
                str(error),
                parent=self.winfo_toplevel(),
            )
            return

        self.result = result
        self._display_result(result)
        message = (
            f"Scanned: {result.folders_scanned}\n"
            f"Empty: {result.empty_folders}\n"
            f"Skipped: {result.skipped_folders}\n"
            f"Elapsed: {result.elapsed_seconds:.2f} sec"
        )
        if result.issues:
            messagebox.showwarning(
                "Finished",
                message,
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showinfo(
                "Finished",
                message,
                parent=self.winfo_toplevel(),
            )

    def delete_selected(self):
        selected_items = self.preview_table.selection()
        if not selected_items:
            messagebox.showwarning(
                "Delete",
                "Select one or more folders.",
                parent=self.winfo_toplevel(),
            )
            return
        if not messagebox.askyesno(
            "Confirm",
            "Move selected folders to the Recycle Bin?",
            parent=self.winfo_toplevel(),
        ):
            return

        deletion = self.service.delete(
            (self._paths_by_item[item] for item in selected_items),
            confirmed=True,
        )
        deleted = set(deletion.deleted_paths)
        for item in selected_items:
            if self._paths_by_item[item] in deleted:
                self.preview_table.delete(item)
                self._paths_by_item.pop(item, None)

        if self.result and deleted:
            remaining = tuple(path for path in self.result.folders if path not in deleted)
            self.result = ScanResult(
                root=self.result.root,
                folders=remaining,
                folders_scanned=self.result.folders_scanned,
                empty_folders=len(remaining),
                skipped_folders=self.result.skipped_folders,
                elapsed_seconds=self.result.elapsed_seconds,
                issues=self.result.issues,
            )
            self._update_statistics(self.result)

        summary = f"{deletion.deleted_count} folder(s) moved to the Recycle Bin."
        if deletion.failures:
            details = "\n".join(
                f"{failure.path}: {failure.reason}"
                for failure in deletion.failures
            )
            messagebox.showwarning(
                "Finished",
                f"{summary}\n\n{deletion.failed_count} folder(s) failed:\n{details}",
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showinfo(
                "Finished",
                summary,
                parent=self.winfo_toplevel(),
            )

    def export_results(self):
        if not self.result or not self.result.folders:
            messagebox.showwarning(
                "Export",
                "Nothing to export.",
                parent=self.winfo_toplevel(),
            )
            return
        filename = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile="Empty_Folders.csv",
        )
        if not filename:
            return
        try:
            self.service.export_csv(self.result.folders, filename)
        except (EmptyFolderError, OSError) as error:
            messagebox.showerror(
                "Export",
                str(error),
                parent=self.winfo_toplevel(),
            )
            return
        messagebox.showinfo(
            "Export",
            "Report exported successfully.",
            parent=self.winfo_toplevel(),
        )

    def _display_result(self, result: ScanResult):
        self.preview_table.delete(*self.preview_table.get_children())
        self._paths_by_item.clear()
        for index, path in enumerate(result.folders):
            item = f"folder_{index}"
            self._paths_by_item[item] = path
            self.preview_table.insert("", "end", iid=item, values=(str(path),))
        self._update_statistics(result)

    def _update_statistics(self, result: ScanResult):
        self.stats_label.configure(
            text=(
                f"Folders: {result.folders_scanned} | "
                f"Empty: {result.empty_folders} | "
                f"Skipped: {result.skipped_folders} | "
                f"Elapsed: {result.elapsed_seconds:.2f} sec"
            )
        )


__all__ = ["EmptyFolderRemoverWindow"]
