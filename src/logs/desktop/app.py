from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    raise SystemExit(
        "Tkinter is required for the desktop app.\n"
        "On Windows, install Python from python.org (tcl/tk included).\n"
        "On Linux, install python3-tk."
    ) from exc

from logs.desktop.service import (
    MODES,
    default_export_stem,
    export_csv_text,
    export_json_text,
    rows_from_payload,
    run_desktop_extract,
)
from logs.ruleset import BUILDING_RATING_FACTORS


class LogsExtractApp(tk.Tk):
    """Native desktop GUI for Building ruleset factor extraction."""

    def __init__(self) -> None:
        super().__init__()
        self.title("LOGS Extract")
        self.geometry("920x640")
        self.minsize(760, 520)
        self.configure(bg="#f3f7f4")

        self._log_path = tk.StringVar(value="")
        self._ruleset = tk.StringVar(value="Building")
        self._mode = tk.StringVar(value="building-factors")
        self._fields = tk.StringVar(value=",".join(BUILDING_RATING_FACTORS[:3]))
        self._status = tk.StringVar(value="Choose a UW ruleset .log file to begin.")
        self._payload: dict[str, Any] | None = None

        self._build_style()
        self._build_layout()
        self._sync_fields_visibility()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Brand.TLabel", font=("Segoe UI", 28, "bold"), background="#f3f7f4")
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"), background="#f3f7f4")
        style.configure("Body.TLabel", font=("Segoe UI", 10), background="#f3f7f4")
        style.configure("Status.TLabel", font=("Segoe UI", 9), background="#f3f7f4")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("Treeview", font=("Consolas", 10), rowheight=26)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, text="LOGS", style="Brand.TLabel").pack(anchor=tk.W)
        ttk.Label(
            root,
            text="Extract Building rating factors from UW ruleset runs.",
            style="Title.TLabel",
        ).pack(anchor=tk.W, pady=(4, 2))
        ttk.Label(
            root,
            text="Native desktop app (no browser). Open a .log, extract, then save JSON/CSV.",
            style="Body.TLabel",
        ).pack(anchor=tk.W, pady=(0, 14))

        form = ttk.LabelFrame(root, text="Extract", padding=12)
        form.pack(fill=tk.X)

        file_row = ttk.Frame(form)
        file_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Entry(file_row, textvariable=self._log_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(file_row, text="Browse…", command=self._browse).pack(side=tk.LEFT)

        opts = ttk.Frame(form)
        opts.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(opts, text="Ruleset").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(opts, textvariable=self._ruleset, width=24).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 12)
        )
        ttk.Label(opts, text="Mode").grid(row=0, column=1, sticky=tk.W)
        mode = ttk.Combobox(
            opts,
            textvariable=self._mode,
            values=list(MODES),
            state="readonly",
            width=22,
        )
        mode.grid(row=1, column=1, sticky=tk.W)
        mode.bind("<<ComboboxSelected>>", lambda _event: self._sync_fields_visibility())

        self._fields_frame = ttk.Frame(form)
        self._fields_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(self._fields_frame, text="Fields (comma-separated)").pack(anchor=tk.W)
        ttk.Entry(self._fields_frame, textvariable=self._fields).pack(fill=tk.X)

        actions = ttk.Frame(form)
        actions.pack(fill=tk.X)
        ttk.Button(
            actions, text="Extract", style="Accent.TButton", command=self._extract
        ).pack(side=tk.LEFT)
        ttk.Button(actions, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Save JSON", command=self._save_json).pack(side=tk.LEFT)
        ttk.Button(actions, text="Save CSV", command=self._save_csv).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Save Excel", command=self._save_excel).pack(side=tk.LEFT)

        ttk.Label(root, textvariable=self._status, style="Status.TLabel").pack(
            anchor=tk.W, pady=(10, 6)
        )

        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("name", "value", "source")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self._tree.heading("name", text="Factor")
        self._tree.heading("value", text="Value")
        self._tree.heading("source", text="Source")
        self._tree.column("name", width=280, anchor=tk.W)
        self._tree.column("value", width=180, anchor=tk.W)
        self._tree.column("source", width=140, anchor=tk.W)
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _sync_fields_visibility(self) -> None:
        if self._mode.get() == "fields":
            self._fields_frame.pack(fill=tk.X, pady=(0, 8))
        else:
            self._fields_frame.pack_forget()

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Select UW ruleset log",
            filetypes=[("Log files", "*.log *.txt"), ("All files", "*.*")],
        )
        if path:
            self._log_path.set(path)

    def _clear(self) -> None:
        self._log_path.set("")
        self._ruleset.set("Building")
        self._mode.set("building-factors")
        self._fields.set(",".join(BUILDING_RATING_FACTORS[:3]))
        self._payload = None
        self._tree.delete(*self._tree.get_children())
        self._status.set("Choose a UW ruleset .log file to begin.")
        self._sync_fields_visibility()

    def _extract(self) -> None:
        path = self._log_path.get().strip()
        if not path:
            messagebox.showwarning("LOGS Extract", "Choose a log file first.")
            return
        try:
            payload = run_desktop_extract(
                path,
                ruleset=self._ruleset.get(),
                mode=self._mode.get(),
                fields=self._fields.get(),
            )
        except Exception as exc:  # noqa: BLE001 - show in UI
            self._payload = None
            self._tree.delete(*self._tree.get_children())
            self._status.set(str(exc))
            messagebox.showerror("LOGS Extract", str(exc))
            return

        self._payload = payload
        self._tree.delete(*self._tree.get_children())
        rows = rows_from_payload(payload)
        for row in rows:
            self._tree.insert("", tk.END, values=(row["name"], row["value"], row["source"]))

        ruleset = payload["rulesets"][0]
        header = payload.get("header") or {}
        self._status.set(
            " · ".join(
                part
                for part in (
                    f"Extracted {len(rows)} values",
                    payload.get("filename"),
                    header.get("policy_no"),
                    f"precondition {ruleset.get('precondition', {}).get('status')}",
                )
                if part
            )
        )

    def _require_payload(self) -> dict[str, Any] | None:
        if not self._payload:
            messagebox.showwarning("LOGS Extract", "Extract a log first.")
            return None
        return self._payload

    def _save_json(self) -> None:
        payload = self._require_payload()
        if not payload:
            return
        path = filedialog.asksaveasfilename(
            title="Save JSON",
            defaultextension=".json",
            initialfile=f"{default_export_stem(payload)}.json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        Path(path).write_text(export_json_text(payload), encoding="utf-8")
        self._status.set(f"Saved JSON → {path}")

    def _save_csv(self) -> None:
        payload = self._require_payload()
        if not payload:
            return
        path = filedialog.asksaveasfilename(
            title="Save CSV",
            defaultextension=".csv",
            initialfile=f"{default_export_stem(payload)}.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        Path(path).write_text(export_csv_text(payload), encoding="utf-8")
        self._status.set(f"Saved CSV → {path}")

    def _save_excel(self) -> None:
        log_path = self._log_path.get().strip()
        if not log_path:
            messagebox.showwarning("LOGS Extract", "Choose a log file first.")
            return
        payload = self._require_payload()
        if not payload:
            return
        header = payload.get("header") or {}
        default_name = f"{header.get('policy_no') or default_export_stem(payload)}.xlsx"
        path = filedialog.asksaveasfilename(
            title="Save Excel (Policywise format)",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            from logs.excel_export import build_excel_from_log

            build_excel_from_log(
                log_path,
                path,
                ruleset=self._ruleset.get() or "Building",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("LOGS Extract", str(exc))
            self._status.set(str(exc))
            return
        self._status.set(f"Saved Excel → {path}")


def main(argv: list[str] | None = None) -> int:
    _ = argv  # reserved for future CLI flags
    app = LogsExtractApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
