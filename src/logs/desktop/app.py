from __future__ import annotations

from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
    raise SystemExit(
        "Tkinter is required for the desktop app.\n"
        "On Windows, install Python from python.org (tcl/tk included).\n"
        "On Linux, install python3-tk."
    ) from exc

from logs.desktop.service import rows_from_payload, run_desktop_extract
from logs.excel_export import build_excel_from_log, collect_all_section_values
from logs.sections import RATING_SECTION_NAMES


class LogsExtractApp(tk.Tk):
    """Desktop app: upload full log + Excel template → filled Excel output."""

    def __init__(self) -> None:
        super().__init__()
        self.title("LOGS Extract")
        self.geometry("980x680")
        self.minsize(820, 560)
        self.configure(bg="#f3f7f4")

        self._log_path = tk.StringVar(value="")
        self._template_path = tk.StringVar(value="")
        self._status = tk.StringVar(
            value="1) Upload the full UW .log   2) Upload the class-code Excel template   "
            "3) Generate Excel"
        )
        self._section_rows: list[dict[str, str]] = []

        self._build_style()
        self._build_layout()

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
            text="Upload log + class-code Excel template → get filled Excel output.",
            style="Title.TLabel",
        ).pack(anchor=tk.W, pady=(4, 2))
        ttk.Label(
            root,
            text=(
                "Extracts Building / BPP / Liability factors and coverage-wise "
                "Sum Insured, Base Rate, Final Rate, and Premium into your template."
            ),
            style="Body.TLabel",
        ).pack(anchor=tk.W, pady=(0, 14))

        form = ttk.LabelFrame(root, text="Inputs", padding=12)
        form.pack(fill=tk.X)

        log_row = ttk.Frame(form)
        log_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(log_row, text="1. Full UW log file", width=22).pack(side=tk.LEFT)
        ttk.Entry(log_row, textvariable=self._log_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(log_row, text="Browse log…", command=self._browse_log).pack(side=tk.LEFT)

        tpl_row = ttk.Frame(form)
        tpl_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(tpl_row, text="2. Class-code Excel", width=22).pack(side=tk.LEFT)
        ttk.Entry(tpl_row, textvariable=self._template_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(tpl_row, text="Browse Excel…", command=self._browse_template).pack(
            side=tk.LEFT
        )

        actions = ttk.Frame(form)
        actions.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(
            actions,
            text="3. Generate Excel",
            style="Accent.TButton",
            command=self._generate_excel,
        ).pack(side=tk.LEFT)
        ttk.Button(actions, text="Preview factors", command=self._preview_factors).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(actions, text="Clear", command=self._clear).pack(side=tk.LEFT)

        ttk.Label(root, textvariable=self._status, style="Status.TLabel").pack(
            anchor=tk.W, pady=(10, 6)
        )

        table_frame = ttk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("section", "factor", "value")
        self._tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self._tree.heading("section", text="Section")
        self._tree.heading("factor", text="Factor")
        self._tree.heading("value", text="Value")
        self._tree.column("section", width=220, anchor=tk.W)
        self._tree.column("factor", width=220, anchor=tk.W)
        self._tree.column("value", width=160, anchor=tk.W)
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _browse_log(self) -> None:
        path = filedialog.askopenfilename(
            title="Select full UW ruleset log",
            filetypes=[("Log files", "*.log *.txt"), ("All files", "*.*")],
        )
        if path:
            self._log_path.set(path)

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(
            title="Select class-code Excel template",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if path:
            self._template_path.set(path)

    def _clear(self) -> None:
        self._log_path.set("")
        self._template_path.set("")
        self._section_rows = []
        self._tree.delete(*self._tree.get_children())
        self._status.set(
            "1) Upload the full UW .log   2) Upload the class-code Excel template   "
            "3) Generate Excel"
        )

    def _require_log(self) -> str | None:
        path = self._log_path.get().strip()
        if not path:
            messagebox.showwarning("LOGS Extract", "Choose the full UW .log file first.")
            return None
        if not Path(path).exists():
            messagebox.showerror("LOGS Extract", f"Log file not found:\n{path}")
            return None
        return path

    def _require_template(self) -> str | None:
        path = self._template_path.get().strip()
        if not path:
            messagebox.showwarning(
                "LOGS Extract",
                "Choose the class-code Excel template (.xlsx) to fill.",
            )
            return None
        if not Path(path).exists():
            messagebox.showerror("LOGS Extract", f"Excel template not found:\n{path}")
            return None
        return path

    def _preview_factors(self) -> None:
        log_path = self._require_log()
        if not log_path:
            return
        try:
            sections = collect_all_section_values(log_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("LOGS Extract", str(exc))
            self._status.set(str(exc))
            return

        self._section_rows = []
        self._tree.delete(*self._tree.get_children())
        count = 0
        for section_name in RATING_SECTION_NAMES:
            values = sections.get(section_name) or {}
            for factor, value in values.items():
                if value is None or str(value).strip() == "":
                    continue
                row = {
                    "section": section_name,
                    "factor": factor,
                    "value": str(value),
                }
                self._section_rows.append(row)
                self._tree.insert(
                    "",
                    tk.END,
                    values=(row["section"], row["factor"], row["value"]),
                )
                count += 1

        # Also show a quick Building factor preview using standard extract if empty.
        if count == 0:
            payload = run_desktop_extract(log_path, ruleset="Building", mode="building-factors")
            for row in rows_from_payload(payload):
                self._tree.insert(
                    "",
                    tk.END,
                    values=("Building", row["name"], row["value"]),
                )
                count += 1

        self._status.set(
            f"Previewed {count} factors from "
            + ", ".join(RATING_SECTION_NAMES)
            + ". Click Generate Excel to write the template."
        )

    def _generate_excel(self) -> None:
        log_path = self._require_log()
        if not log_path:
            return
        template_path = self._require_template()
        if not template_path:
            return

        # Refresh preview while generating.
        try:
            self._preview_factors()
        except Exception:  # noqa: BLE001
            pass

        default_name = f"{Path(log_path).stem}.xlsx"
        # Prefer policy-looking token from filename if present.
        stem = Path(log_path).name
        if "PMBP" in stem.upper():
            default_name = stem.split("_")[0] + ".xlsx"

        out_path = filedialog.asksaveasfilename(
            title="Save filled Excel output",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not out_path:
            return

        try:
            dest = build_excel_from_log(
                log_path,
                out_path,
                template=template_path,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("LOGS Extract", str(exc))
            self._status.set(str(exc))
            return

        self._status.set(f"Saved filled Excel → {dest}")
        messagebox.showinfo(
            "LOGS Extract",
            "Excel generated successfully.\n\n"
            f"Log: {Path(log_path).name}\n"
            f"Template: {Path(template_path).name}\n"
            f"Output: {dest}",
        )


def main(argv: list[str] | None = None) -> int:
    _ = argv
    app = LogsExtractApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
