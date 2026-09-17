"""Tkinter GUI for Easy Alpha Check."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from typing import Any

from PIL import Image, ImageTk

from .analyzer import AlphaCheckError, analyze_image
from .preview import render_preview

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:  # Click-to-open remains available without the optional DnD package.
    DND_FILES = None
    TkinterDnD = None


APP_BG = "#F7F4EE"
SURFACE = "#FFFDF9"
INK = "#3F4652"
MUTED = "#515762"
BORDER = "#E4DED4"
ASSET_DIR = Path(__file__).resolve().parent / "assets"

RESULT_ORDER = (
    "TRUE_TRANSPARENT",
    "PARTIAL_TRANSPARENCY_ONLY",
    "ALPHA_CHANNEL_ONLY",
    "NO_ALPHA_CHANNEL",
)

RESULTS = {
    "TRUE_TRANSPARENT": {
        "title": "TRUE TRANSPARENT",
        "short": "本物の透過",
        "description": "実際に完全透明なピクセルが存在します。\nFully transparent pixels are present.",
        "accent": "#4F9368",
        "soft": "#EAF5EC",
        "asset": "elf_true_transparent.png",
    },
    "PARTIAL_TRANSPARENCY_ONLY": {
        "title": "PARTIAL TRANSPARENCY ONLY",
        "short": "半透明のみ",
        "description": (
            "半透明ピクセルは存在しますが、完全透明なピクセルはありません。\n"
            "Semi-transparent pixels exist, but no fully transparent pixels were found."
        ),
        "accent": "#B48332",
        "soft": "#FBF2DC",
        "asset": "elf_partial_transparency.png",
    },
    "ALPHA_CHANNEL_ONLY": {
        "title": "ALPHA CHANNEL EXISTS",
        "short": "Alphaのみ",
        "description": (
            "Alphaチャンネルはありますが、すべてのピクセルが完全不透明です。\n"
            "An alpha channel exists, but every pixel is fully opaque."
        ),
        "accent": "#7771AB",
        "soft": "#EFEDF8",
        "asset": "elf_alpha_only.png",
    },
    "NO_ALPHA_CHANNEL": {
        "title": "NO ALPHA CHANNEL",
        "short": "Alphaなし",
        "description": "この画像にはAlphaチャンネルがありません。\nThis image has no alpha channel.",
        "accent": "#B76868",
        "soft": "#F9EDED",
        "asset": "elf_no_alpha.png",
    },
}


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def _load_scaled_asset(file_name: str, max_size: tuple[int, int]) -> ImageTk.PhotoImage:
    with Image.open(ASSET_DIR / file_name) as source:
        image = source.convert("RGBA")
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(image)


class AlphaCheckApp(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(22, 18), style="App.TFrame")
        self.master = master
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="alphacheck")
        self.current_path: Path | None = None
        self.current_result: dict[str, Any] | None = None
        self.alpha_map = False
        self.photo: ImageTk.PhotoImage | None = None
        self.preview_after_id: str | None = None
        self.job_token = 0
        self.elf_small: dict[str, ImageTk.PhotoImage] = {}
        self.elf_large: dict[str, ImageTk.PhotoImage] = {}
        self.result_cards: dict[str, tk.Frame] = {}
        self.ui_font = self._pick_font(("Yu Gothic UI", "Meiryo UI", "Meiryo", "Noto Sans CJK JP"))
        self.title_font = self._pick_font(("Segoe UI Black", "Arial Rounded MT Bold", "Segoe UI"))

        self._configure_styles()
        self._load_elf_assets()
        self._build_ui()
        self.pack(fill="both", expand=True)
        self.master.protocol("WM_DELETE_WINDOW", self._close)

    def _pick_font(self, preferred: tuple[str, ...]) -> str:
        available = {name.casefold(): name for name in tkfont.families(self.master)}
        for name in preferred:
            if name.casefold() in available:
                return available[name.casefold()]
        return str(tkfont.nametofont("TkDefaultFont").actual("family"))

    def _configure_styles(self) -> None:
        style = ttk.Style(self.master)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("App.TFrame", background=APP_BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("Subtitle.TLabel", background=APP_BG, foreground=MUTED, font=(self.ui_font, 10))
        style.configure(
            "Soft.TButton",
            background="#EEE9E0",
            foreground=INK,
            bordercolor="#DCD5CA",
            focusthickness=0,
            padding=(12, 7),
            font=(self.ui_font, 9, "bold"),
        )
        style.map("Soft.TButton", background=[("active", "#E6DED2")])
        style.configure(
            "Primary.TButton",
            background="#719A7B",
            foreground="#FFFFFF",
            bordercolor="#719A7B",
            focusthickness=0,
            padding=(16, 9),
            font=(self.ui_font, 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#5E8769")])
        for style_name, background, active in (
            ("Map.TButton", "#8B80C4", "#796DB7"),
            ("Clear.TButton", "#DE8585", "#CF7474"),
            ("Open.TButton", "#67A77C", "#55946A"),
        ):
            style.configure(
                style_name,
                background=background,
                foreground="#FFFFFF",
                bordercolor=background,
                focusthickness=0,
                padding=(13, 8),
                font=(self.ui_font, 9, "bold"),
            )
            style.map(
                style_name,
                background=[("active", active), ("disabled", "#C9C5C0")],
                foreground=[("disabled", "#F5F3EF")],
            )
        style.configure("Warm.Horizontal.TProgressbar", background="#82A98A", troughcolor="#E8E2D8")

    def _load_elf_assets(self) -> None:
        self.app_icon = _load_scaled_asset("app_icon.png", (48, 48))
        for classification, info in RESULTS.items():
            self.elf_small[classification] = _load_scaled_asset(info["asset"], (76, 90))
            self.elf_large[classification] = _load_scaled_asset(info["asset"], (122, 148))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        title_row = ttk.Frame(header, style="App.TFrame")
        title_row.grid(row=0, column=0, sticky="w")
        tk.Label(title_row, image=self.app_icon, background=APP_BG, borderwidth=0).pack(side="left", padx=(0, 9))
        tk.Label(
            title_row,
            text="Easy Alpha Check",
            background=APP_BG,
            foreground="#3C7E6F",
            font=(self.title_font, 24, "bold"),
            borderwidth=0,
        ).pack(side="left")
        ttk.Label(
            header,
            text=(
                "画像に本当の透明があるか、4人のエルフがそっと見分けます。\n"
                "Four elves gently check whether your image has real transparency."
            ),
            style="Subtitle.TLabel",
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.card_strip = ttk.Frame(self, style="App.TFrame")
        self.card_strip.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for column in range(4):
            self.card_strip.columnconfigure(column, weight=1, uniform="result-card")
        self._build_result_cards()

        self.content = ttk.Frame(self, style="App.TFrame")
        self.content.grid(row=2, column=0, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self._build_welcome()
        self._build_results()

        footer = ttk.Frame(self, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(11, 0))
        footer.columnconfigure(0, weight=1)
        self.status = ttk.Label(footer, text=self._drop_status_text(), style="Subtitle.TLabel")
        self.status.grid(row=0, column=0, sticky="w")
        ttk.Label(
            footer,
            text="画像は変更されません / Images are never modified",
            style="Subtitle.TLabel",
        ).grid(row=0, column=1, sticky="e")
        self.progress = ttk.Progressbar(self, mode="indeterminate", style="Warm.Horizontal.TProgressbar")

        self._register_drop_targets()

    def _build_result_cards(self) -> None:
        for column, classification in enumerate(RESULT_ORDER):
            info = RESULTS[classification]
            card = tk.Frame(
                self.card_strip,
                background=info["soft"],
                highlightbackground=BORDER,
                highlightcolor=info["accent"],
                highlightthickness=1,
                borderwidth=0,
                padx=9,
                pady=8,
            )
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
            card.columnconfigure(0, weight=1)
            tk.Label(card, image=self.elf_small[classification], background=info["soft"], borderwidth=0).grid(
                row=0, column=0
            )
            tk.Label(
                card,
                text=info["short"],
                background=info["soft"],
                foreground=info["accent"],
                font=(self.ui_font, 10, "bold"),
                anchor="center",
            ).grid(row=1, column=0, sticky="ew", pady=(1, 0))
            short_code = info["title"]
            tk.Label(
                card,
                text=short_code,
                background=info["soft"],
                foreground="#535862",
                font=(self.title_font, 8, "bold"),
                justify="center",
                anchor="center",
            ).grid(row=2, column=0, sticky="ew", pady=(2, 0))
            self.result_cards[classification] = card

    def _build_welcome(self) -> None:
        self.welcome = tk.Frame(
            self.content,
            background=SURFACE,
            highlightbackground=BORDER,
            highlightthickness=1,
            borderwidth=0,
            cursor="hand2",
        )
        self.welcome.grid(row=0, column=0, sticky="nsew")
        self.welcome.columnconfigure(0, weight=1)
        self.welcome.rowconfigure(0, weight=1)
        drop_inner = tk.Frame(self.welcome, background=SURFACE, cursor="hand2")
        drop_inner.grid(row=0, column=0)
        tk.Label(
            drop_inner,
            text="画像をここへドロップ\nDrop an image here",
            background=SURFACE,
            foreground=INK,
            font=(self.ui_font, 17, "bold"),
            cursor="hand2",
        ).pack(pady=(0, 7))
        tk.Label(
            drop_inner,
            text="PNG / WebP / JPEG / BMP / TIFF\nクリックして選択 / Or click to browse",
            background=SURFACE,
            foreground=MUTED,
            font=(self.ui_font, 10, "bold"),
            justify="center",
            cursor="hand2",
        ).pack(pady=(0, 16))
        ttk.Button(
            drop_inner,
            text="画像を選択 / Choose Image",
            command=self.choose_file,
            style="Primary.TButton",
        ).pack()
        for widget in (self.welcome, drop_inner):
            widget.bind("<Button-1>", lambda _event: self.choose_file())

    def _build_results(self) -> None:
        self.results = ttk.Frame(self.content, style="App.TFrame")
        self.results.columnconfigure(0, weight=1, minsize=450, uniform="main-pane")
        self.results.columnconfigure(1, weight=1, minsize=480, uniform="main-pane")
        self.results.rowconfigure(0, weight=1)

        preview_surface = tk.Frame(
            self.results,
            background=SURFACE,
            highlightbackground=BORDER,
            highlightthickness=1,
            borderwidth=0,
            padx=14,
            pady=13,
        )
        preview_surface.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        preview_surface.columnconfigure(0, weight=1)
        preview_surface.rowconfigure(1, weight=1)
        tk.Label(
            preview_surface,
            text="Preview",
            background=SURFACE,
            foreground=INK,
            font=(self.ui_font, 11, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.preview_label = tk.Label(preview_surface, anchor="center", background="#ECE8E0", borderwidth=0)
        self.preview_label.grid(row=1, column=0, sticky="nsew")
        self.preview_label.bind("<Configure>", self._on_preview_resize)

        preview_buttons = ttk.Frame(preview_surface, style="Surface.TFrame")
        preview_buttons.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        for column in range(3):
            preview_buttons.columnconfigure(column, weight=1, uniform="preview-button")
        self.alpha_button = ttk.Button(
            preview_buttons,
            text="透過シルエット\nTransparency Map",
            command=self.toggle_alpha_map,
            style="Map.TButton",
            width=19,
        )
        self.alpha_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(
            preview_buttons,
            text="画像をクリア\nClear",
            command=self.clear_image,
            style="Clear.TButton",
            width=19,
        ).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(
            preview_buttons,
            text="別の画像\nOpen Another",
            command=self.choose_file,
            style="Open.TButton",
            width=19,
        ).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        details = tk.Frame(
            self.results,
            background=SURFACE,
            highlightbackground=BORDER,
            highlightthickness=1,
            borderwidth=0,
            padx=15,
            pady=13,
        )
        details.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        details.columnconfigure(0, weight=1)
        details.rowconfigure(1, weight=1, minsize=365)

        hero = tk.Frame(details, background=SURFACE, height=166)
        hero.grid(row=0, column=0, sticky="ew")
        hero.grid_propagate(False)
        hero.columnconfigure(2, weight=1)
        hero.rowconfigure(0, weight=1)
        text_area = tk.Frame(hero, background=SURFACE)
        text_area.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.result_title = tk.Label(
            text_area,
            font=(self.title_font, 13, "bold"),
            anchor="w",
            justify="left",
            background=SURFACE,
        )
        self.result_title.pack(anchor="w")
        self.result_description = tk.Label(
            text_area,
            background=SURFACE,
            foreground=INK,
            font=(self.ui_font, 9, "bold"),
            anchor="w",
            justify="left",
        )
        self.result_description.pack(anchor="w", pady=(7, 0))
        self.result_elf = tk.Label(hero, background=SURFACE, borderwidth=0)
        self.result_elf.grid(row=0, column=1, sticky="w", padx=(4, 0))

        self.info_text = tk.Text(
            details,
            width=39,
            height=22,
            borderwidth=0,
            highlightthickness=0,
            font=("Consolas", 9),
            foreground=INK,
            background=SURFACE,
            cursor="arrow",
            wrap="none",
        )
        self.info_text.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.info_text.configure(state="disabled")

    def _drop_status_text(self) -> str:
        if DND_FILES is None:
            return "クリックで画像を選択できます。 / Click to choose an image."
        return "画像をウィンドウへドロップできます。 / Drop an image anywhere in this window."

    def _register_drop_targets(self) -> None:
        if DND_FILES is None:
            return
        for widget in (self, self.welcome, self.results, self.preview_label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event: Any) -> None:
        paths = self.master.tk.splitlist(event.data)
        if paths:
            self.load_file(paths[0])

    def choose_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="検査する画像を選択 / Choose an image",
            filetypes=[
                ("画像ファイル / Image Files", "*.png *.webp *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("すべてのファイル / All Files", "*.*"),
            ],
        )
        if selected:
            self.load_file(selected)

    def clear_image(self) -> None:
        self.job_token += 1
        if self.preview_after_id:
            self.after_cancel(self.preview_after_id)
            self.preview_after_id = None
        self.current_path = None
        self.current_result = None
        self.alpha_map = False
        self.photo = None
        self.preview_label.configure(image="", text="")
        self.result_elf.configure(image="")
        self.alpha_button.configure(text="透過シルエット\nTransparency Map", state="normal")
        self.results.grid_remove()
        self.welcome.grid(row=0, column=0, sticky="nsew")
        self._highlight_result(None)
        self._finish_progress()
        self.status.configure(text=self._drop_status_text())

    def load_file(self, path: str | Path) -> None:
        self.job_token += 1
        token = self.job_token
        candidate = Path(path)
        self.status.configure(text=f"解析中 / Analyzing: {candidate.name}")
        self.progress.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.progress.start(10)
        future = self.executor.submit(analyze_image, candidate)

        def completed() -> None:
            if token != self.job_token:
                return
            try:
                result = future.result()
            except AlphaCheckError as exc:
                self._finish_progress()
                self.status.configure(text="画像を解析できませんでした。 / Analysis failed.")
                messagebox.showerror("Easy Alpha Check", str(exc), parent=self.master)
                return
            except Exception as exc:  # Keep the GUI alive on unexpected decoder errors.
                self._finish_progress()
                self.status.configure(text="予期しないエラーが発生しました。 / Unexpected error.")
                messagebox.showerror(
                    "Easy Alpha Check",
                    f"画像を解析できませんでした。\nCould not analyze this image.\n\n{exc}",
                    parent=self.master,
                )
                return
            self.current_path = candidate
            self.current_result = result
            self.alpha_map = False
            self.alpha_button.configure(text="透過シルエット\nTransparency Map")
            self._finish_progress()
            self._show_result(result)
            self._refresh_preview()

        self._poll_future(future, completed)

    def _poll_future(self, future: Any, callback: Any) -> None:
        if future.done():
            callback()
        else:
            self.after(35, self._poll_future, future, callback)

    def _finish_progress(self) -> None:
        self.progress.stop()
        self.progress.grid_remove()

    def _highlight_result(self, selected: str | None) -> None:
        for classification, card in self.result_cards.items():
            info = RESULTS[classification]
            is_selected = classification == selected
            card.configure(
                highlightbackground=info["accent"] if is_selected else BORDER,
                highlightthickness=3 if is_selected else 1,
            )

    def _show_result(self, result: dict[str, Any]) -> None:
        self.welcome.grid_remove()
        self.results.grid(row=0, column=0, sticky="nsew")
        classification = result["classification"]
        info = RESULTS[classification]
        single_line = classification == "TRUE_TRANSPARENT"
        self.result_title.configure(
            text=info["title"],
            foreground=info["accent"],
            wraplength=0 if single_line else 340,
        )
        self.result_description.configure(
            text=info["description"],
            wraplength=0 if single_line else 340,
        )
        self.result_elf.configure(image=self.elf_large[classification])
        self._highlight_result(classification)
        self.alpha_button.configure(state="normal" if result["has_alpha"] else "disabled")

        bounds = result["content_bounds"]
        if bounds is None:
            bounds_text = "None (fully transparent)"
        else:
            left, top, right, bottom = bounds
            bounds_text = f"X: {left:,} - {right:,}\nY: {top:,} - {bottom:,}"

        if result["has_alpha"]:
            alpha_lines = [
                f"Alpha Range       {result['alpha_min']} - {result['alpha_max']}",
                "",
                "Fully Transparent",
                f"  {result['transparent_pixels']:,} px   {result['transparent_percent']:.2f} %",
                "Semi Transparent",
                f"  {result['semi_transparent_pixels']:,} px   {result['semi_transparent_percent']:.2f} %",
                "Fully Opaque",
                f"  {result['opaque_pixels']:,} px   {result['opaque_percent']:.2f} %",
            ]
        else:
            alpha_lines = ["Alpha Range       —", "", "Alpha pixel statistics are unavailable."]

        lines = [
            "IMAGE INFORMATION",
            "",
            f"File Name         {result['file_name']}",
            f"Format            {result['format']}",
            f"Dimensions        {result['width']:,} × {result['height']:,}",
            f"Color Mode        {result['mode']}",
            f"File Size         {_human_size(result['file_size'])}",
            "",
            "ALPHA INFORMATION",
            "",
            *alpha_lines,
            "",
            "CONTENT BOUNDS",
            "",
            bounds_text,
        ]
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", "\n".join(lines))
        self.info_text.configure(state="disabled")
        self.status.configure(text=f"解析完了 / Complete: {result['file_name']}（読み取り専用 / Read only）")

    def toggle_alpha_map(self) -> None:
        if not self.current_result or not self.current_result["has_alpha"]:
            return
        self.alpha_map = not self.alpha_map
        self.alpha_button.configure(
            text="通常表示\nNormal Preview" if self.alpha_map else "透過シルエット\nTransparency Map"
        )
        self._refresh_preview()

    def _on_preview_resize(self, _event: Any) -> None:
        if not self.current_path:
            return
        if self.preview_after_id:
            self.after_cancel(self.preview_after_id)
        self.preview_after_id = self.after(180, self._refresh_preview)

    def _refresh_preview(self) -> None:
        self.preview_after_id = None
        if not self.current_path:
            return
        width = max(100, self.preview_label.winfo_width() - 16)
        height = max(100, self.preview_label.winfo_height() - 16)
        path = self.current_path
        alpha_map = self.alpha_map
        token = self.job_token
        future = self.executor.submit(render_preview, path, (width, height), alpha_map=alpha_map)

        def completed() -> None:
            if token != self.job_token or path != self.current_path or alpha_map != self.alpha_map:
                return
            try:
                preview = future.result()
            except Exception:
                self.preview_label.configure(text="プレビューを表示できません。\nPreview unavailable.", image="")
                return
            self.photo = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self.photo, text="")

        self._poll_future(future, completed)

    def _close(self) -> None:
        self.job_token += 1
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.master.destroy()


def main() -> None:
    root_class = TkinterDnD.Tk if TkinterDnD is not None else tk.Tk
    root = root_class()
    root.title("Easy Alpha Check")
    root.geometry("1080x920")
    root.minsize(1040, 900)
    root.configure(background=APP_BG)
    try:
        icon = tk.PhotoImage(file=str(ASSET_DIR / "app_icon.png"))
        root.iconphoto(True, icon)
        root._easy_alpha_check_icon = icon
        root.iconname("Easy Alpha Check")
    except (tk.TclError, OSError):
        pass
    AlphaCheckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
