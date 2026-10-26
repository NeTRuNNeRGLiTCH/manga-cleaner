"""
Page Renamer
Renames sequential page files: stitched_001.jpg -> 1.jpg  |  stitched_028.png -> 28.png

Requirements:  pip install customtkinter
Build exe:     python -m PyInstaller --onefile --noconsole --collect-all customtkinter page_renamer.py
"""

import os
import re
import uuid
from tkinter import filedialog

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

EXTENSIONS = ("jpg", "jpeg", "png", "webp")

# Log colors
GREEN = "#00ff80"
RED = "#ff5555"
YELLOW = "#ffcc00"
CYAN = "#4fc3f7"
GRAY = "#8a8a8a"

LINE = "━" * 46


class PageRenamer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Page Renamer v1.1")
        self.geometry("740x600")
        self.minsize(640, 500)

        self.folder = ""

        # ---------- Side panel ----------
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="CONTROL PANEL",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(20, 10))

        box = ctk.CTkFrame(self.sidebar, fg_color="#1e1e1e")
        box.pack(padx=15, pady=10, fill="x")
        ctk.CTkLabel(box, text="FILES RENAMED",
                     font=ctk.CTkFont(size=11)).pack(pady=(10, 0))
        self.lbl_counter = ctk.CTkLabel(
            box, text="0", text_color=GREEN,
            font=ctk.CTkFont(size=40, weight="bold"))
        self.lbl_counter.pack(pady=(0, 10))

        self.btn_folder = ctk.CTkButton(
            self.sidebar, text="SELECT FOLDER", command=self.select_folder)
        self.btn_folder.pack(padx=15, pady=(15, 6), fill="x")

        self.btn_rename = ctk.CTkButton(
            self.sidebar, text="RENAME", fg_color="green",
            hover_color="#0b6b0b", command=self.rename_files, state="disabled")
        self.btn_rename.pack(padx=15, pady=6, fill="x")

        self.btn_clear = ctk.CTkButton(
            self.sidebar, text="CLEAR LOG", fg_color="#444444",
            hover_color="#555555", command=self.clear_log)
        self.btn_clear.pack(padx=15, pady=6, fill="x")

        # ---------- Main panel ----------
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        self.lbl_status = ctk.CTkLabel(
            self.main, text="WAITING...", height=70,
            fg_color="#3a3a3a", corner_radius=12,
            font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_status.pack(fill="x")

        self.progress = ctk.CTkProgressBar(self.main, progress_color=GREEN, height=8)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(10, 0))

        row = ctk.CTkFrame(self.main, fg_color="transparent")
        row.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(row, text="Prefix to remove:").pack(side="left")
        self.entry_prefix = ctk.CTkEntry(row, width=140)
        self.entry_prefix.insert(0, "stitched_")
        self.entry_prefix.pack(side="left", padx=8)

        self.lbl_folder = ctk.CTkLabel(
            self.main, text="No folder selected",
            anchor="w", text_color="#aaaaaa")
        self.lbl_folder.pack(fill="x", pady=(8, 4))

        self.log = ctk.CTkTextbox(
            self.main, font=ctk.CTkFont(family="Consolas", size=12))
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        # Log text styles
        self.log.tag_config("ok", foreground=GREEN)
        self.log.tag_config("error", foreground=RED)
        self.log.tag_config("title", foreground=YELLOW)
        self.log.tag_config("info", foreground=CYAN)
        self.log.tag_config("dim", foreground=GRAY)

        self.welcome_message()

    # ---------- log ----------
    def write(self, parts):
        """parts: plain string or a list of (text, tag) tuples."""
        if isinstance(parts, str):
            parts = [(parts, None)]
        self.log.configure(state="normal")
        for text, tag in parts:
            if tag:
                self.log.insert("end", text, tag)
            else:
                self.log.insert("end", text)
        self.log.insert("end", "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def header(self, title, tag="title"):
        self.write([(LINE, "dim")])
        self.write([(f"  {title}", tag)])
        self.write([(LINE, "dim")])

    def welcome_message(self):
        self.header("PAGE RENAMER", "info")
        self.write([("  1. ", "dim"), ("Select the folder with your images", None)])
        self.write([("  2. ", "dim"), ("Review the preview", None)])
        self.write([("  3. ", "dim"), ("Click RENAME", None)])
        self.write("")
        self.write([("  stitched_001.jpg  →  1.jpg", "dim")])

    def clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def set_status(self, text, color=None):
        self.lbl_status.configure(text=text)
        if color:
            self.lbl_status.configure(text_color=color)

    # ---------- logic ----------
    def build_pattern(self):
        prefix = re.escape(self.entry_prefix.get())
        return re.compile(rf"^{prefix}(\d+)\.({'|'.join(EXTENSIONS)})$", re.IGNORECASE)

    def find_candidates(self):
        """Returns a list of (original_name, new_name)."""
        pattern = self.build_pattern()
        result = []
        for name in os.listdir(self.folder):
            m = pattern.match(name)
            if m:
                new_name = f"{int(m.group(1))}.{m.group(2).lower()}"
                result.append((name, new_name))
        result.sort(key=lambda t: int(re.search(r"\d+", t[1]).group()))
        return result

    # ---------- actions ----------
    def select_folder(self):
        path = filedialog.askdirectory(title="Select the folder with the pages")
        if not path:
            return
        self.folder = path
        self.lbl_folder.configure(text=path)
        self.lbl_counter.configure(text="0")
        self.progress.set(0)
        candidates = self.find_candidates()
        self.clear_log()

        if not candidates:
            self.header("NO FILES FOUND", "error")
            self.write([("  No files matching that pattern were found.", "dim")])
            self.btn_rename.configure(state="disabled")
            self.set_status("NO FILES", "#ffb020")
            return

        self.header(f"PREVIEW  ·  {len(candidates)} files")
        width = max(len(old) for old, _ in candidates)
        for old, new in candidates:
            self.write([
                ("  ", None),
                (old.ljust(width), "dim"),
                ("  →  ", "info"),
                (new, "ok"),
            ])
        self.write("")
        self.write([("  All set. Click RENAME to apply.", "info")])
        self.btn_rename.configure(state="normal")
        self.set_status("READY", GREEN)

    def rename_files(self):
        if not self.folder:
            return
        candidates = self.find_candidates()
        if not candidates:
            self.set_status("NO FILES", "#ffb020")
            return

        self.btn_rename.configure(state="disabled")
        self.btn_folder.configure(state="disabled")
        self.set_status("RENAMING...", "#2196f3")
        self.progress.set(0)
        self.clear_log()
        self.header("RENAMING", "title")
        self.update_idletasks()

        total = len(candidates)
        width = max(len(old) for old, _ in candidates)

        # Step 1: temporary names (avoids collisions if "1.jpg", etc. already exists)
        temp_files = []
        errors = 0
        for old, new in candidates:
            tmp = f"__tmp_{uuid.uuid4().hex}_{new}"
            try:
                os.rename(os.path.join(self.folder, old),
                          os.path.join(self.folder, tmp))
                temp_files.append((old, tmp, new))
            except OSError as e:
                errors += 1
                self.write([("  ✘ ", "error"), (old, "dim"), (f"  {e}", "error")])

        # Step 2: final names
        done = 0
        for i, (old, tmp, new) in enumerate(temp_files, start=1):
            destination = os.path.join(self.folder, new)
            try:
                if os.path.exists(destination):
                    raise FileExistsError(f"{new} already exists")
                os.rename(os.path.join(self.folder, tmp), destination)
                done += 1
                self.write([
                    ("  ✔ ", "ok"),
                    (old.ljust(width), "dim"),
                    ("  →  ", "info"),
                    (new, "ok"),
                ])
                self.lbl_counter.configure(text=str(done))
            except OSError as e:
                errors += 1
                os.rename(os.path.join(self.folder, tmp),
                          os.path.join(self.folder, old))  # restore original name
                self.write([
                    ("  ✘ ", "error"),
                    (old.ljust(width), "dim"),
                    (f"  {e} (name restored)", "error"),
                ])
            self.progress.set(i / total)
            self.update_idletasks()

        self.write("")
        self.header("SUMMARY", "ok" if not errors else "error")
        self.write([
            ("  ✔ Renamed: ", "ok"), (str(done), None),
            ("     ✘ Errors: ", "error" if errors else "dim"), (str(errors), None),
        ])
        self.write([("  Folder: ", "dim"), (os.path.basename(self.folder), "info")])

        self.btn_folder.configure(state="normal")
        if errors:
            self.set_status("FINISHED WITH ERRORS", "#ffb020")
        else:
            self.set_status("COMPLETED", GREEN)


if __name__ == "__main__":
    PageRenamer().mainloop()