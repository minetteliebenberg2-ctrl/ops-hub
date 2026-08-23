"""Native FC Hub window for the Batch Renamer."""

from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from gui.design_tokens import COLORS
from modules.batch_renamer.services import RenamePreview, build_preview, execute_rename


class BatchRenamerWindow(ctk.CTkFrame):
    columns = ("original", "proposed", "status", "details")

    def __init__(self, master):
        super().__init__(master)
        self.selected_folder = ""
        self.preview: RenamePreview | None = None
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Batch Renamer", font=("Segoe UI", 22, "bold")).pack(pady=(18, 5))
        ctk.CTkLabel(self, text="Preview and safely rename files.").pack(pady=(0, 12))

        folder_row = ctk.CTkFrame(self)
        folder_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(folder_row, text="Choose Folder", command=self.choose_folder, width=130).pack(side="left", padx=5, pady=8)
        self.folder_label = ctk.CTkLabel(folder_row, text="No folder selected", anchor="w")
        self.folder_label.pack(side="left", fill="x", expand=True, padx=8)

        prefix_row = ctk.CTkFrame(self)
        prefix_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(prefix_row, text="Prefix").pack(side="left", padx=8)
        self.prefix_entry = ctk.CTkEntry(prefix_row, width=260)
        self.prefix_entry.pack(side="left", padx=8, pady=8)
        self.prefix_entry.bind("<KeyRelease>", self.invalidate_preview)

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.preview_table = ttk.Treeview(table_frame, columns=self.columns, show="headings", height=15)
        headings = {"original": "Original Filename", "proposed": "Proposed Filename", "status": "Status", "details": "Details"}
        widths = {"original": 270, "proposed": 270, "status": 100, "details": 420}
        for column in self.columns:
            self.preview_table.heading(column, text=headings[column])
            self.preview_table.column(column, width=widths[column], minwidth=90, anchor="w", stretch=column == "details")
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
        ctk.CTkButton(button_row, text="Preview", command=self.build_preview, width=130).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(button_row, text="Rename Files", command=self.rename_files, width=130).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(button_row, text="Reset", command=self.reset, width=110, fg_color=COLORS["button_secondary"], hover_color=COLORS["button_secondary_hover"]).pack(side="left", padx=5, pady=8)
        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.pack(fill="x", padx=20, pady=(3, 12))

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.winfo_toplevel())
        if not folder:
            return
        self.selected_folder = folder
        self.folder_label.configure(text=folder)
        self.invalidate_preview()
        self.build_preview()

    def invalidate_preview(self, _event=None):
        self.preview = None
        self.status_label.configure(text="Preview invalidated; generate a new preview.")

    def reset(self):
        self.selected_folder = ""
        self.preview = None
        self.folder_label.configure(text="No folder selected")
        self.prefix_entry.delete(0, "end")
        self.preview_table.delete(*self.preview_table.get_children())
        self.status_label.configure(text="Ready")

    def build_preview(self):
        self.preview = build_preview(self.selected_folder, self.prefix_entry.get())
        self.preview_table.delete(*self.preview_table.get_children())
        for item in self.preview.items:
            self.preview_table.insert("", "end", values=(item.original_name, item.proposed_name, item.status, item.details))
        for skipped in self.preview.skipped:
            self.preview_table.insert("", "end", values=(skipped.path.name, "—", "Skipped", skipped.reason))
        if self.preview.valid:
            self.status_label.configure(text=f"Preview ready: {len(self.preview.items)} file(s); {len(self.preview.skipped)} skipped.")
        else:
            self.status_label.configure(text=self._issue_text(self.preview.issues) or "Preview contains blocking validation errors.")

    def rename_files(self):
        if self.preview is None:
            messagebox.showwarning("Batch Renamer", "Generate a valid preview before renaming.", parent=self.winfo_toplevel())
            return
        if not self.preview.valid:
            messagebox.showerror("Batch Renamer", self._issue_text(self.preview.issues) or "The preview is not valid.", parent=self.winfo_toplevel())
            return
        if not messagebox.askyesno(
            "Confirm Rename",
            f"Folder:\n{self.selected_folder}\n\nRename {len(self.preview.items)} file(s)?\n\nFilenames on disk will change.",
            parent=self.winfo_toplevel(),
        ):
            self.status_label.configure(text="Rename cancelled; no files changed.")
            return
        result = execute_rename(self.preview, self.selected_folder, self.prefix_entry.get())
        if result.validation_issues:
            messagebox.showerror("Batch Renamer", "The preview is stale or no longer valid.\n\n" + self._issue_text(result.validation_issues), parent=self.winfo_toplevel())
            self.preview = None
            self.status_label.configure(text="Preview stale; generate a new preview.")
            return
        report = self._execution_text(result)
        if result.failed_count:
            messagebox.showwarning("Batch Renamer - Partial Completion", report, parent=self.winfo_toplevel())
            self.status_label.configure(text="Rename stopped after an unexpected failure.")
        elif result.renamed_count:
            messagebox.showinfo("Batch Renamer - Complete", report, parent=self.winfo_toplevel())
            self.status_label.configure(text=f"Renamed {result.renamed_count} file(s); {result.skipped_count} skipped.")
        else:
            messagebox.showwarning("Batch Renamer", report, parent=self.winfo_toplevel())
            self.status_label.configure(text="No files were renamed.")
        self.preview = None

    @staticmethod
    def _issue_text(issues):
        return "\n".join(f"• {issue.message}" for issue in issues)

    @staticmethod
    def _execution_text(result):
        lines = [f"Attempted: {result.attempted_count}", f"Renamed: {result.renamed_count}", f"Skipped: {result.skipped_count}", f"Failed: {result.failed_count}"]
        if result.failed_file:
            lines.append(f"Failed file: {result.failed_file[0]}\nError: {result.error_details}")
        if result.not_processed:
            lines.append("Not processed:\n" + "\n".join(str(source) for source, _ in result.not_processed))
        if result.skipped_files:
            lines.append("Skipped:\n" + "\n".join(f"{item.path}: {item.reason}" for item in result.skipped_files))
        return "\n\n".join(lines)
