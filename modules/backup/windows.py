"""Native CustomTkinter dashboard for the FC Hub Backup module."""

from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from modules.backup.services import BackupService, BackupSummary, ExternalDriveInfo


class BackupWindow(ctk.CTkFrame):
    """Small-screen-friendly dashboard with no direct filesystem logic."""

    columns = ("created", "size", "status", "verification", "path")

    def __init__(self, master, service: BackupService | None = None):
        super().__init__(master)
        self.service = service or BackupService()
        self.destination = self.service.default_destination
        self._summaries: list[BackupSummary] = []
        self._build_ui()
        self.refresh_history()

    def _build_ui(self):
        ctk.CTkLabel(self, text="FC Hub Backup", font=("Segoe UI", 22, "bold")).pack(pady=(18, 4))
        ctk.CTkLabel(self, text="Create verified backups and prepare guarded restores.").pack(pady=(0, 12))

        destination_row = ctk.CTkFrame(self)
        destination_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(destination_row, text="Choose Destination", command=self.choose_destination, width=150).pack(side="left", padx=5, pady=8)
        self.destination_label = ctk.CTkLabel(destination_row, text=str(self.destination), anchor="w")
        self.destination_label.pack(side="left", fill="x", expand=True, padx=8)

        action_row = ctk.CTkFrame(self)
        action_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(action_row, text="Create Backup", command=self.create_backup, width=130).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Backup to External Drive", command=self.backup_to_external_drive, width=190).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Refresh", command=self.refresh_history, width=100).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Verify Backup", command=self.verify_selected, width=130).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="Prepare Restore", command=self.prepare_restore, width=140).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(action_row, text="View Manifest", command=self.view_manifest, width=130).pack(side="left", padx=5, pady=8)

        retention_row = ctk.CTkFrame(self)
        retention_row.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(retention_row, text="Retention review (days)").pack(side="left", padx=8)
        self.retention_entry = ctk.CTkEntry(retention_row, width=80)
        self.retention_entry.insert(0, str(self.service.retention_days))
        self.retention_entry.pack(side="left", padx=5, pady=8)
        ctk.CTkButton(retention_row, text="Show Cleanup Candidates", command=self.show_cleanup_candidates, width=180).pack(side="left", padx=5, pady=8)

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.history_table = ttk.Treeview(table_frame, columns=self.columns, show="headings", selectmode="browse")
        headings = {"created": "Date Created", "size": "Backup Size", "status": "Status", "verification": "Verification", "path": "Backup Folder"}
        widths = {"created": 180, "size": 110, "status": 100, "verification": 110, "path": 420}
        for column in self.columns:
            self.history_table.heading(column, text=headings[column])
            self.history_table.column(column, width=widths[column], minwidth=90, anchor="w", stretch=column == "path")
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.history_table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.history_table.xview)
        self.history_table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.history_table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.pack(fill="x", padx=20, pady=(3, 12))

    def choose_destination(self):
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), title="Choose Backup Destination")
        if not folder:
            return
        self.destination = Path(folder).resolve()
        self.destination_label.configure(text=str(self.destination))
        self.refresh_history()

    def create_backup(self):
        if not messagebox.askyesno("Create Backup", f"Create a verified full backup in:\n{self.destination}?", parent=self.winfo_toplevel()):
            self.status_label.configure(text="Backup cancelled; no files changed.")
            return
        result = self.service.create_backup(self.destination)
        if result.success:
            messagebox.showinfo("Backup Complete", result.message + f"\n\n{result.backup_path}", parent=self.winfo_toplevel())
        else:
            messagebox.showerror("Backup Failed", result.message + "\n\nAn incomplete staging folder, if created, was retained for review.", parent=self.winfo_toplevel())
        self.status_label.configure(text=result.message)
        self.refresh_history()

    def backup_to_external_drive(self):
        drives = self.service.list_external_drives()
        if not drives:
            messagebox.showinfo(
                "Backup to External Drive",
                "No external drive was detected. Connect a USB drive or external hard drive, "
                "then try again.",
                parent=self.winfo_toplevel(),
            )
            return
        drive = ExternalDriveDialog.ask(self.winfo_toplevel(), drives)
        if drive is None:
            return
        destination = drive.root / "FC_Hub_Backups"
        if not messagebox.askyesno(
            "Backup to External Drive",
            f"Create a verified full backup on {drive.display_name}?\n\nDestination:\n{destination}",
            parent=self.winfo_toplevel(),
        ):
            self.status_label.configure(text="Backup to external drive cancelled; no files changed.")
            return
        result = self.service.create_backup(destination)
        if result.success:
            messagebox.showinfo("Backup Complete", result.message + f"\n\n{result.backup_path}", parent=self.winfo_toplevel())
        else:
            messagebox.showerror("Backup Failed", result.message + "\n\nAn incomplete staging folder, if created, was retained for review.", parent=self.winfo_toplevel())
        self.status_label.configure(text=result.message)
        self.destination = destination
        self.destination_label.configure(text=str(self.destination))
        self.refresh_history()

    def refresh_history(self):
        self._summaries = self.service.list_backups(self.destination)
        self.history_table.delete(*self.history_table.get_children())
        for index, summary in enumerate(self._summaries):
            item_id = str(index)
            self.history_table.insert(
                "",
                "end",
                iid=item_id,
                values=(summary.created_at, self._format_size(summary.size), summary.status, summary.verification_status, str(summary.path)),
            )
        self.status_label.configure(text=f"{len(self._summaries)} backup(s) listed. No cleanup is automatic.")

    def _selected_summary(self) -> BackupSummary | None:
        selection = self.history_table.selection()
        if not selection:
            messagebox.showwarning("Backup", "Select a backup first.", parent=self.winfo_toplevel())
            return None
        index = int(selection[0])
        return self._summaries[index]

    def verify_selected(self):
        summary = self._selected_summary()
        if not summary:
            return
        result = self.service.verify_backup(summary.path)
        level = messagebox.showinfo if result.success else messagebox.showerror
        level("Backup Verification", result.message, parent=self.winfo_toplevel())
        self.status_label.configure(text=result.message)

    def view_manifest(self):
        summary = self._selected_summary()
        if not summary:
            return
        manifest_path = summary.path / "manifest.json"
        try:
            text = manifest_path.read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("Manifest", f"Could not read manifest: {error}", parent=self.winfo_toplevel())
            return
        window = ctk.CTkToplevel(self.winfo_toplevel())
        window.title("Backup Manifest")
        window.geometry("800x600")
        box = ctk.CTkTextbox(window, wrap="none")
        box.pack(fill="both", expand=True, padx=10, pady=10)
        box.insert("1.0", text)
        box.configure(state="disabled")

    def prepare_restore(self):
        summary = self._selected_summary()
        if not summary:
            return
        preview = self.service.prepare_restore(summary.path)
        if not preview.valid:
            messagebox.showerror("Restore Preview", preview.message, parent=self.winfo_toplevel())
            return
        lines = [
            preview.message,
            f"Files: {len(preview.files)}",
            f"Would overwrite: {len(preview.overwrites)}",
            f"Sensitive files: {len(preview.sensitive_files)}",
            "\nNo restore was performed. FC Hub must be closed before any real restore.",
        ]
        messagebox.showinfo("Restore Preview", "\n".join(lines), parent=self.winfo_toplevel())
        self.status_label.configure(text="Restore preview ready; no files changed.")

    def show_cleanup_candidates(self):
        try:
            self.service.retention_days = max(0, int(self.retention_entry.get()))
        except ValueError:
            messagebox.showerror("Retention", "Retention days must be a whole number.", parent=self.winfo_toplevel())
            return
        candidates = self.service.cleanup_candidates(self.destination)
        if candidates:
            detail = "\n".join(str(item.path) for item in candidates)
            messagebox.showinfo("Cleanup Candidates", "Review only; nothing was deleted.\n\n" + detail, parent=self.winfo_toplevel())
        else:
            messagebox.showinfo("Cleanup Candidates", "No verified backups are currently eligible. Nothing was deleted.", parent=self.winfo_toplevel())

    @staticmethod
    def _format_size(value: int) -> str:
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{value} B"


class ExternalDriveDialog(ctk.CTkToplevel):
    """Modal picker for the detected external drives; returns the chosen drive or None."""

    def __init__(self, master, drives: list[ExternalDriveInfo]):
        super().__init__(master)
        self.title("Choose External Drive")
        self.geometry("520x320")
        self.transient(master)
        self.grab_set()
        self.drives = drives
        self.selected: ExternalDriveInfo | None = None

        ctk.CTkLabel(self, text="Select the external drive to back up to:", anchor="w").pack(fill="x", padx=15, pady=(15, 8))

        self.choice = ctk.StringVar(value=drives[0].letter)
        list_frame = ctk.CTkScrollableFrame(self)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)
        for drive in drives:
            ctk.CTkRadioButton(list_frame, text=drive.display_name, variable=self.choice, value=drive.letter).pack(anchor="w", pady=4, padx=5)

        button_row = ctk.CTkFrame(self)
        button_row.pack(fill="x", padx=15, pady=15)
        ctk.CTkButton(button_row, text="Cancel", command=self._cancel, width=100).pack(side="right", padx=5)
        ctk.CTkButton(button_row, text="Select", command=self._confirm, width=100).pack(side="right", padx=5)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _confirm(self):
        letter = self.choice.get()
        self.selected = next((drive for drive in self.drives if drive.letter == letter), None)
        self.destroy()

    def _cancel(self):
        self.selected = None
        self.destroy()

    @classmethod
    def ask(cls, master, drives: list[ExternalDriveInfo]) -> ExternalDriveInfo | None:
        dialog = cls(master, drives)
        dialog.wait_window()
        return dialog.selected


__all__ = ["BackupWindow", "ExternalDriveDialog"]
