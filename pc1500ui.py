#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc1500ui.py —— PC-1500 audio/BASIC conversion GUI (tkinter, no third-party deps)

Features:
  1. MIDI -> BEEP music BASIC      (calls midi2beep_pc1500.py)
  2. BASIC -> cassette WAV         (calls bas2wav / bin2wav)
  3. cassette WAV -> BASIC         (calls wav2bas / wav2bin)
  4. image -> CE-150 drawing BASIC (calls img2lines.py)

Run:  ./pc1500ui.py
"""

import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"
BAS2WAV = os.path.join(HERE, "bas2wav")
WAV2BAS = os.path.join(HERE, "wav2bas")
IMG2LINES = os.path.join(HERE, "img2lines.py")
MIDI2BEEP = os.path.join(HERE, "midi2beep_pc1500.py")


# ---------------------------------------------------------------- i18n
TEXTS = {
    "zh": {
        "title": "PC-1500 音频 / BASIC 转换工具",
        "header": "PC-1500 音频 / BASIC 转换工具",
        "subtitle": "MIDI → BEEP 音乐，BASIC ↔ 磁带音频，图片 → CE-150 绘图",
        "lang_btn": "English",
        "log_title": "输出",
        "status_ready": "就绪",
        "status_busy": "处理中…",
        "status_running": "运行中…",
        "status_done": "完成",
        "status_failed": "失败",
        "status_previewing": "预览中…",
        "status_preview_done": "预览完成（%d 条线）",
        "status_preview_failed": "预览失败",
        "browse": "浏览…",

        "tab_midi": "  MIDI → BEEP 音乐  ",
        "tab_bas2wav": "  BASIC → 磁带 WAV  ",
        "tab_wav2bas": "  磁带 WAV → BASIC  ",
        "tab_img": "  图片 → 打印机绘图  ",

        # MIDI tab
        "midi_hint": "把 MIDI 文件转成 PC-1500 的 BEEP 音乐 BASIC。"
                     "多轨文件默认自动选主旋律轨，也可以手动指定。",
        "midi_in": "MIDI 文件",
        "midi_out": "输出 .bas",
        "midi_track": "轨道",
        "midi_track_auto": "自动",
        "midi_list_tracks": "列出轨道",
        "midi_go": "生成 BASIC",
        "midi_note": "说明：蜂鸣器只能单音，和弦只保留最高音。频率参数映射到"
             "PC-1500 的 value2 范围 0~255（约 230 Hz ~ 7 kHz），超出范围的"
             "音符会被钳制到边界。生成后用「BASIC → 磁带 WAV」转成音频再 CLOAD。",
        # BASIC -> WAV tab
        "b2w_hint": "把 BASIC 程序编成磁带音频，用 CE-150 的 EAR 口放给 PC-1500 的 CLOAD 听。",
        "b2w_in": "BASIC",
        "b2w_out": "输出 .wav",
        "b2w_name": "保存名",
        "b2w_sync": "同步",
        "b2w_sec": "秒",
        "b2w_rate": "采样率",
        "b2w_note": "保存名 = 真机上 CLOAD \"名字\" 用的名字（最多 16 字符）；"
                    "采样率 48k 最稳，读不出时依次试 48k / 16k / 44k。",
        "b2w_go": "生成 WAV",
        "b2w_go_play": "生成后播放",

        # WAV -> BASIC tab
        "w2b_hint": "把 PC-1500 用 CSAVE 录出来的音频还原成 BASIC 源码。",
        "w2b_in": "录音文件",
        "w2b_out": "输出 .bas",
        "w2b_dev": "录音来源",
        "w2b_dev_auto": "自动",
        "w2b_dev_hint": "（磁带机直录用 CAS；蜂鸣器外录用 AIR；模拟器录的音用 EMU）",
        "w2b_go": "还原成 BASIC",
        "w2b_go_img": "同时导出中间码 .img",
        "w2b_note": "录音要求：采样率至少 11025 Hz，单声道，尽量 16-bit，"
                    "幅度接近但别过载，别剪掉开头的引导音。",

        # Image tab
        "img_hint": "把图片变成线条画，生成 CE-150 打印机能画的 BASIC 程序。",
        "img_in": "图片",
        "img_out": "输出 .bas",
        "img_mode": "模式",
        "img_mode_hint": "（edge=照片边缘 / mono=线稿深色部分）",
        "img_thr": "阈值",
        "img_invert": "反色",
        "img_side": "细节",
        "img_side_hint": "（数值越大线越多越细，程序也越长）",
        "img_simpl": "抽稀",
        "img_simpl_hint": "（越大线越少；程序太长时调大）",
        "img_preview": "① 预览线条",
        "img_go": "② 生成 BASIC",
        "img_go_wav": "生成并转 WAV",
        "img_preview_frame": "预览（按 CE-150 真实纸带比例）",
        "img_note": "CE-150 有效绘图区：横向约 216 步（43.2mm），纵向约 512 步"
                    "（102.4mm），每步 0.2mm。预览里的纸带和留白就是实机效果。",

        # dialogs
        "dlg_missing_in": "缺少输入",
        "dlg_missing_in_midi": "先选一个 MIDI 文件。",
        "dlg_missing_in_img": "先选一张图片。",
        "dlg_missing_in_bas": "先选一个 BASIC 文件。",
        "dlg_missing_in_wav": "先选一个录音文件。",
        "dlg_not_found": "找不到文件",
        "dlg_not_found_img": "找不到图片",

        "fd_midi": "选择 MIDI",
        "fd_image": "选择图片",
        "fd_wav_in": "选择录音",
        "fd_bas_in": "选择 BASIC 源文件",
        "fd_save_bas": "保存 BASIC 为",
        "fd_save_wav": "保存 WAV 为",
        "ft_all": "所有文件",
        "ft_midi": "MIDI",
        "ft_image": "图片",
        "ft_audio": "音频",
        "ft_basic": "BASIC",
        "ft_wav": "WAV",

        "log_title_midi": "MIDI → BEEP BASIC",
        "log_list_tracks": "列出 MIDI 轨道",
        "log_bas2wav": "BASIC → WAV",
        "log_img2bas": "图片 → 绘图 BASIC",
        "log_img2wav": "绘图 BASIC → WAV",
        "log_wav2bas": "WAV → BASIC",
        "log_preview": "预览线条",
        "log_no_player": "没找到 ffplay/aplay，无法自动播放，请手动打开文件。\n",
        "log_preview_failed": "预览失败: %s\n",
        "log_lines": "线条 %d 条，纸带 %d x %d 步\n",
        "log_preview_err": "没有提取到线条，试试调低阈值或换成 mono 模式",
        "log_done": "\n[完成] %s\n",
        "log_failed": "\n[失败] %s，返回码 %d\n",
        "log_start_failed": "启动失败: %s\n",
        "log_cmd_prefix": "$ ",
        "log_section": "\n=== %s ===\n",
        "canvas_info": "纸带 %d×%d 步 / %d 条线 (%.1f×%.1f mm)",
    },
    "en": {
        "title": "PC-1500 Audio / BASIC Converter",
        "header": "PC-1500 Audio / BASIC Converter",
        "subtitle": "MIDI → BEEP music, BASIC ↔ cassette audio, image → CE-150 drawing",
        "lang_btn": "简体中文",
        "log_title": "Output",
        "status_ready": "Ready",
        "status_busy": "Working…",
        "status_running": "Running…",
        "status_done": "Done",
        "status_failed": "Failed",
        "status_previewing": "Previewing…",
        "status_preview_done": "Preview done (%d lines)",
        "status_preview_failed": "Preview failed",
        "browse": "Browse…",

        "tab_midi": "  MIDI → BEEP Music  ",
        "tab_bas2wav": "  BASIC → Cassette WAV  ",
        "tab_wav2bas": "  Cassette WAV → BASIC  ",
        "tab_img": "  Image → Printer Drawing  ",

        "midi_hint": "Convert a MIDI file into a PC-1500 BEEP music BASIC program. "
                     "Multi-track files auto-pick the main melody by default; "
                     "you can also specify a track manually.",
        "midi_in": "MIDI file",
        "midi_out": "Output .bas",
        "midi_track": "Track",
        "midi_track_auto": "Auto",
        "midi_list_tracks": "List tracks",
        "midi_go": "Generate BASIC",
        "midi_note": "Note: the beeper is monophonic; chords keep only the top note. "
             "Frequency parameters are mapped to the PC-1500's value2 range 0~255 "
             "(roughly 230 Hz ~ 7 kHz); notes outside it are clamped to the edge. "
             "After generating, use \"BASIC → Cassette WAV\" to make audio, then CLOAD.",

        "b2w_hint": "Compile a BASIC program into cassette audio, play it into the "
                    "CE-150's EAR input for the PC-1500 to CLOAD.",
        "b2w_in": "BASIC",
        "b2w_out": "Output .wav",
        "b2w_name": "Save name",
        "b2w_sync": "Sync",
        "b2w_sec": "s",
        "b2w_rate": "Sample rate",
        "b2w_note": "Save name = the name the real machine's CLOAD \"name\" uses "
                    "(max 16 chars). 48k is most reliable; if it won't load, try "
                    "48k / 16k / 44k in turn.",
        "b2w_go": "Generate WAV",
        "b2w_go_play": "Generate & play",

        "w2b_hint": "Restore audio recorded via CSAVE on the PC-1500 back into BASIC source.",
        "w2b_in": "Recording",
        "w2b_out": "Output .bas",
        "w2b_dev": "Source",
        "w2b_dev_auto": "Auto",
        "w2b_dev_hint": "(CAS = direct from cassette deck; AIR = over the air from a beeper; EMU = recorded in an emulator)",
        "w2b_go": "Restore BASIC",
        "w2b_go_img": "Also export .img intermediate",
        "w2b_note": "Recording requirements: at least 11025 Hz, mono, 16-bit preferred, "
                    "amplitude close to but not overloading, don't cut the leading tone.",

        "img_hint": "Turn an image into a line drawing and generate BASIC the CE-150 printer can draw.",
        "img_in": "Image",
        "img_out": "Output .bas",
        "img_mode": "Mode",
        "img_mode_hint": "(edge = photo edges / mono = dark areas of line art)",
        "img_thr": "Threshold",
        "img_invert": "Invert",
        "img_side": "Detail",
        "img_side_hint": "(larger = more/finer lines, longer program)",
        "img_simpl": "Simplify",
        "img_simpl_hint": "(larger = fewer lines; raise if the program is too long)",
        "img_preview": "① Preview lines",
        "img_go": "② Generate BASIC",
        "img_go_wav": "Generate & WAV",
        "img_preview_frame": "Preview (true CE-150 paper proportions)",
        "img_note": "CE-150 drawing area: about 216 steps wide (43.2mm) and 512 steps "
                    "tall (102.4mm), 0.2mm per step. The paper strip and margins in the "
                    "preview match the real machine.",

        "dlg_missing_in": "Missing input",
        "dlg_missing_in_midi": "Pick a MIDI file first.",
        "dlg_missing_in_img": "Pick an image first.",
        "dlg_missing_in_bas": "Pick a BASIC file first.",
        "dlg_missing_in_wav": "Pick a recording first.",
        "dlg_not_found": "File not found",
        "dlg_not_found_img": "Image not found",

        "fd_midi": "Choose MIDI",
        "fd_image": "Choose image",
        "fd_wav_in": "Choose recording",
        "fd_bas_in": "Choose BASIC source",
        "fd_save_bas": "Save BASIC as",
        "fd_save_wav": "Save WAV as",
        "ft_all": "All files",
        "ft_midi": "MIDI",
        "ft_image": "Images",
        "ft_audio": "Audio",
        "ft_basic": "BASIC",
        "ft_wav": "WAV",

        "log_title_midi": "MIDI → BEEP BASIC",
        "log_list_tracks": "List MIDI tracks",
        "log_bas2wav": "BASIC → WAV",
        "log_img2bas": "Image → drawing BASIC",
        "log_img2wav": "Drawing BASIC → WAV",
        "log_wav2bas": "WAV → BASIC",
        "log_preview": "Preview lines",
        "log_no_player": "No ffplay/aplay found; cannot auto-play. Open the file manually.\n",
        "log_preview_failed": "Preview failed: %s\n",
        "log_lines": "%d lines, paper strip %d x %d steps\n",
        "log_preview_err": "No lines extracted; try a lower threshold or mono mode",
        "log_done": "\n[Done] %s\n",
        "log_failed": "\n[Failed] %s, return code %d\n",
        "log_start_failed": "Failed to start: %s\n",
        "log_cmd_prefix": "$ ",
        "log_section": "\n=== %s ===\n",
        "canvas_info": "Paper %d×%d steps / %d lines (%.1f×%.1f mm)",
    },
}


def preview_lines(img_path, params):
    """Compute line preview via img2lines.py functions.

    Returns (segs, paper_w, paper_h, err):
        segs coordinates lie within paper strip [0, paper_w] × [0, paper_h] (Y already flipped).
    """
    if not os.path.exists(IMG2LINES):
        return None, 0, 0, "img2lines.py not found (%s)" % IMG2LINES
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("img2lines", IMG2LINES)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        return None, 0, 0, "Failed to load img2lines.py: %s" % e

    try:
        mode = params.get("mode", "edge")
        threshold = int(params.get("threshold", 128))
        max_side = int(params.get("max_side", 420))
        simplify = float(params.get("simplify", 1.0))
        invert = bool(params.get("invert", False))

        plot_w = getattr(mod, "X_MAX", 216)
        plot_h = getattr(mod, "Y_MAX", 512)

        w, h, px = mod.read_gray(img_path, max_side)
        mask = mod.to_binary(w, h, px, mode, threshold, blur=1, invert=invert)
        mask = mod.thin(mod.dilate(mask, w, h, 1), w, h)
        segs = mod.to_segments(mask, w, h, simplify)
        if not segs:
            return None, 0, 0, "no-lines"

        segs, pw, ph = mod.map_to_plot(segs, w, h, plot_w, plot_h, True)
        return segs, pw, ph, None
    except SystemExit as e:
        return None, 0, 0, "img2lines exited: %s" % (e.code if e.code else e)
    except Exception as e:  # noqa: BLE001
        return None, 0, 0, "preview_lines() error: %s" % e


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.lang = "zh"
        self.outq = queue.Queue()
        self.busy = False
        self._ui = {}

        self._build_ui()
        self.after(100, self._drain_queue)

    # ---------------------------------------------------------------- i18n
    def t(self, key):
        return TEXTS[self.lang].get(key, key)

    def _set_lang(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self._apply_texts()

    def _apply_texts(self):
        self.title(self.t("title"))
        for widget, key in self._ui.get("labels", []):
            try:
                widget.configure(text=self.t(key))
            except tk.TclError:
                pass
        for widget, key in self._ui.get("buttons", []):
            try:
                widget.configure(text=self.t(key))
            except tk.TclError:
                pass
        for widget, key in self._ui.get("frames", []):
            try:
                widget.configure(text=self.t(key))
            except tk.TclError:
                pass
        for widget, key in self._ui.get("notebooks", []):
            pass  # tabs re-labeled below
        for nb, pages in self._ui.get("tabs", []):
            for i, key in enumerate(pages):
                try:
                    nb.tab(i, text=self.t(key))
                except tk.TclError:
                    pass
        if not self.busy:
            self.status.configure(text=self.t("status_ready"))
        self.lang_btn.configure(text=self.t("lang_btn"))
        # combobox default values
        self.md_track_combo.configure(values=[self.t("midi_track_auto")])
        self.r_dev_combo.configure(values=[
            self.t("w2b_dev_auto"), "CAS", "AIR", "EMU"])
        if self.md_track.get() in ("自动", "Auto"):
            self.md_track.set(self.t("midi_track_auto"))
        if self.r_dev.get() in ("自动", "Auto"):
            self.r_dev.set(self.t("w2b_dev_auto"))

    def _reg(self, kind, widget, key):
        self._ui.setdefault(kind, []).append((widget, key))
        return widget

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self, padding=(12, 10, 12, 4))
        header.pack(fill="x")
        topbar = ttk.Frame(header)
        topbar.pack(fill="x")
        self.header_lbl = self._reg("labels", ttk.Label(
            topbar, text=self.t("header"), font=("", 14, "bold")), "header")
        self.header_lbl.pack(side="left", anchor="w")
        self.lang_btn = ttk.Button(topbar, text=self.t("lang_btn"),
                                   command=self._set_lang, width=10)
        self.lang_btn.pack(side="right")
        self.subtitle_lbl = self._reg("labels", ttk.Label(
            header, text=self.t("subtitle"), foreground="#555"), "subtitle")
        self.subtitle_lbl.pack(anchor="w")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=6)

        self._tab_midi = self._build_midi_tab(nb)
        nb.add(self._tab_midi, text=self.t("tab_midi"))

        self._tab_to_wav = self._build_bas2wav_tab(nb)
        nb.add(self._tab_to_wav, text=self.t("tab_bas2wav"))

        self._tab_from_wav = self._build_wav2bas_tab(nb)
        nb.add(self._tab_from_wav, text=self.t("tab_wav2bas"))

        self._tab_img = self._build_image_tab(nb)
        nb.add(self._tab_img, text=self.t("tab_img"))

        self._ui.setdefault("tabs", []).append(
            (nb, ["tab_midi", "tab_bas2wav", "tab_wav2bas", "tab_img"]))

        logf = ttk.LabelFrame(self, text=self.t("log_title"), padding=6)
        self._reg("frames", logf, "log_title")
        logf.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.log = tk.Text(logf, height=8, wrap="word", state="disabled",
                           font=("monospace", 9), background="#f8f8f8")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(self, padding=(12, 2, 12, 8))
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text=self.t("status_ready"))
        self.status.pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self.progress.pack(side="right")

    def _row(self, parent, label_key, var, cmd, width=58):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        lbl = ttk.Label(f, text=self.t(label_key), width=10)
        self._reg("labels", lbl, label_key)
        lbl.pack(side="left")
        e = ttk.Entry(f, textvariable=var, width=width)
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        b = ttk.Button(f, text=self.t("browse"), command=cmd)
        self._reg("buttons", b, "browse")
        b.pack(side="left")
        return e

    # ---------------------------------------------------------- MIDI → BEEP
    def _build_midi_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.md_midi = tk.StringVar()
        self.md_out = tk.StringVar()

        hint = ttk.Label(f, text=self.t("midi_hint"), foreground="#444")
        self._reg("labels", hint, "midi_hint")
        hint.pack(anchor="w", pady=(0, 8))

        self._row(f, "midi_in", self.md_midi, self._pick_midi)
        self._row(f, "midi_out", self.md_out, self._pick_bas_out_midi)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        lbl_track = ttk.Label(opt, text=self.t("midi_track"))
        self._reg("labels", lbl_track, "midi_track")
        lbl_track.pack(side="left")
        self.md_track = tk.StringVar(value=self.t("midi_track_auto"))
        self.md_track_combo = ttk.Combobox(opt, textvariable=self.md_track,
                                           state="normal", width=8,
                                           values=[self.t("midi_track_auto")])
        self.md_track_combo.pack(side="left", padx=(4, 14))
        b = ttk.Button(opt, text=self.t("midi_list_tracks"), command=self._list_midi_tracks)
        self._reg("buttons", b, "midi_list_tracks")
        b.pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.md_btn_go = ttk.Button(btns, text=self.t("midi_go"), command=self._run_midi)
        self._reg("buttons", self.md_btn_go, "midi_go")
        self.md_btn_go.pack(side="left")

        ttk.Separator(f).pack(fill="x", pady=10)
        note = ttk.Label(f, text=self.t("midi_note"),
                         foreground="#777", wraplength=740, justify="left")
        self._reg("labels", note, "midi_note")
        note.pack(anchor="w")
        return f

    def _pick_midi(self):
        p = filedialog.askopenfilename(
            title=self.t("fd_midi"),
            filetypes=[(self.t("ft_midi"), "*.mid *.midi"), (self.t("ft_all"), "*")])
        if p:
            self.md_midi.set(p)
            if not self.md_out.get():
                self.md_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_out_midi(self):
        p = filedialog.asksaveasfilename(title=self.t("fd_save_bas"), defaultextension=".bas",
                                         filetypes=[(self.t("ft_basic"), "*.bas")])
        if p:
            self.md_out.set(p)

    def _midi_argv(self):
        src = self.md_midi.get().strip()
        if not src:
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_midi"))
            return None
        if not os.path.exists(src):
            messagebox.showerror(self.t("dlg_not_found"), src)
            return None
        out = self.md_out.get().strip() or (os.path.splitext(src)[0] + ".bas")
        argv = [PY, MIDI2BEEP, src, out]
        tr = self.md_track.get().strip()
        if tr and tr not in ("自动", "Auto"):
            argv += ["--track", tr]
        return argv, out

    def _run_midi(self):
        r = self._midi_argv()
        if r:
            self._run_cmd(r[0], self.t("log_title_midi"))

    def _list_midi_tracks(self):
        src = self.md_midi.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_midi"))
            return
        self._run_cmd([PY, MIDI2BEEP, "--list-tracks", src], self.t("log_list_tracks"))

    # ---------------------------------------------------------- BASIC → WAV
    def _build_bas2wav_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.w_bas = tk.StringVar()
        self.w_out = tk.StringVar()

        hint = ttk.Label(f, text=self.t("b2w_hint"), foreground="#444")
        self._reg("labels", hint, "b2w_hint")
        hint.pack(anchor="w", pady=(0, 8))
        self._row(f, "b2w_in", self.w_bas, self._pick_bas_in)
        self._row(f, "b2w_out", self.w_out, self._pick_wav_out)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        lbl = ttk.Label(opt, text=self.t("b2w_name"))
        self._reg("labels", lbl, "b2w_name")
        lbl.pack(side="left")
        self.w_name = tk.StringVar()
        ttk.Entry(opt, textvariable=self.w_name, width=18).pack(side="left", padx=(4, 14))
        lbl = ttk.Label(opt, text=self.t("b2w_sync"))
        self._reg("labels", lbl, "b2w_sync")
        lbl.pack(side="left")
        self.w_sync = tk.StringVar(value="2.0")
        ttk.Entry(opt, textvariable=self.w_sync, width=6).pack(side="left", padx=(4, 2))
        lbl = ttk.Label(opt, text=self.t("b2w_sec"))
        self._reg("labels", lbl, "b2w_sec")
        lbl.pack(side="left", padx=(0, 10))
        lbl = ttk.Label(opt, text=self.t("b2w_rate"))
        self._reg("labels", lbl, "b2w_rate")
        lbl.pack(side="left")
        self.w_rate = tk.StringVar(value="48k")
        ttk.Combobox(opt, textvariable=self.w_rate, state="readonly", width=6,
                     values=["48k", "16k", "44k", "10k"]).pack(side="left", padx=(4, 4))

        note = ttk.Label(f, text=self.t("b2w_note"),
                         foreground="#666", wraplength=740, justify="left")
        self._reg("labels", note, "b2w_note")
        note.pack(anchor="w", pady=(6, 0))

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.w_btn = ttk.Button(btns, text=self.t("b2w_go"), command=self._run_bas2wav)
        self._reg("buttons", self.w_btn, "b2w_go")
        self.w_btn.pack(side="left")
        b = ttk.Button(btns, text=self.t("b2w_go_play"), command=self._run_bas2wav_and_play)
        self._reg("buttons", b, "b2w_go_play")
        b.pack(side="left", padx=6)
        return f

    # ---------------------------------------------------------- WAV → BASIC
    def _build_wav2bas_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.r_wav = tk.StringVar()
        self.r_out = tk.StringVar()

        hint = ttk.Label(f, text=self.t("w2b_hint"), foreground="#444")
        self._reg("labels", hint, "w2b_hint")
        hint.pack(anchor="w", pady=(0, 8))
        self._row(f, "w2b_in", self.r_wav, self._pick_wav_in)
        self._row(f, "w2b_out", self.r_out, self._pick_bas_out2)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        lbl = ttk.Label(opt, text=self.t("w2b_dev"))
        self._reg("labels", lbl, "w2b_dev")
        lbl.pack(side="left")
        self.r_dev = tk.StringVar(value=self.t("w2b_dev_auto"))
        self.r_dev_combo = ttk.Combobox(opt, textvariable=self.r_dev, state="readonly", width=8,
                                        values=[self.t("w2b_dev_auto"), "CAS", "AIR", "EMU"])
        self.r_dev_combo.pack(side="left", padx=(4, 14))
        lbl = ttk.Label(opt, text=self.t("w2b_dev_hint"), foreground="#666")
        self._reg("labels", lbl, "w2b_dev_hint")
        lbl.pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.r_btn = ttk.Button(btns, text=self.t("w2b_go"), command=self._run_wav2bas)
        self._reg("buttons", self.r_btn, "w2b_go")
        self.r_btn.pack(side="left")
        b = ttk.Button(btns, text=self.t("w2b_go_img"),
                       command=lambda: self._run_wav2bas(also_img=True))
        self._reg("buttons", b, "w2b_go_img")
        b.pack(side="left", padx=6)

        ttk.Separator(f).pack(fill="x", pady=10)
        note = ttk.Label(f, text=self.t("w2b_note"),
                         foreground="#777", wraplength=740, justify="left")
        self._reg("labels", note, "w2b_note")
        note.pack(anchor="w")
        return f

    # ---------------------------------------------------------- 图片 → 绘图
    def _build_image_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.i_img = tk.StringVar()
        self.i_out = tk.StringVar()

        hint = ttk.Label(f, text=self.t("img_hint"), foreground="#444")
        self._reg("labels", hint, "img_hint")
        hint.pack(anchor="w", pady=(0, 8))

        self._row(f, "img_in", self.i_img, self._pick_image)
        self._row(f, "img_out", self.i_out, self._pick_bas_out3)

        r1 = ttk.Frame(f)
        r1.pack(fill="x", pady=(8, 3))
        lbl = ttk.Label(r1, text=self.t("img_mode"))
        self._reg("labels", lbl, "img_mode")
        lbl.pack(side="left")
        self.i_mode = tk.StringVar(value="edge")
        ttk.Combobox(r1, textvariable=self.i_mode, state="readonly", width=6,
                     values=["edge", "mono"]).pack(side="left", padx=(4, 4))
        lbl = ttk.Label(r1, text=self.t("img_mode_hint"), foreground="#666")
        self._reg("labels", lbl, "img_mode_hint")
        lbl.pack(side="left", padx=(0, 14))
        lbl = ttk.Label(r1, text=self.t("img_thr"))
        self._reg("labels", lbl, "img_thr")
        lbl.pack(side="left")
        self.i_thr = tk.StringVar(value="128")
        ttk.Spinbox(r1, textvariable=self.i_thr, from_=10, to=250, width=5,
                    increment=10).pack(side="left", padx=(4, 2))
        self.i_invert = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(r1, text=self.t("img_invert"), variable=self.i_invert)
        self._reg("buttons", cb, "img_invert")
        cb.pack(side="left", padx=(10, 0))

        r2 = ttk.Frame(f)
        r2.pack(fill="x", pady=3)
        lbl = ttk.Label(r2, text=self.t("img_side"))
        self._reg("labels", lbl, "img_side")
        lbl.pack(side="left")
        self.i_side = tk.StringVar(value="420")
        ttk.Spinbox(r2, textvariable=self.i_side, from_=80, to=900, width=5,
                    increment=20).pack(side="left", padx=(4, 2))
        lbl = ttk.Label(r2, text=self.t("img_side_hint"), foreground="#666")
        self._reg("labels", lbl, "img_side_hint")
        lbl.pack(side="left")

        r3 = ttk.Frame(f)
        r3.pack(fill="x", pady=3)
        lbl = ttk.Label(r3, text=self.t("img_simpl"))
        self._reg("labels", lbl, "img_simpl")
        lbl.pack(side="left")
        self.i_simpl = tk.StringVar(value="1.0")
        ttk.Spinbox(r3, textvariable=self.i_simpl, from_=0.3, to=5.0, width=5,
                    increment=0.2).pack(side="left", padx=(4, 2))
        lbl = ttk.Label(r3, text=self.t("img_simpl_hint"), foreground="#666")
        self._reg("labels", lbl, "img_simpl_hint")
        lbl.pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.i_btn_preview = ttk.Button(btns, text=self.t("img_preview"),
                                        command=self._preview_image)
        self._reg("buttons", self.i_btn_preview, "img_preview")
        self.i_btn_preview.pack(side="left")
        self.i_btn_go = ttk.Button(btns, text=self.t("img_go"), command=self._run_image)
        self._reg("buttons", self.i_btn_go, "img_go")
        self.i_btn_go.pack(side="left", padx=6)
        b = ttk.Button(btns, text=self.t("img_go_wav"),
                       command=lambda: self._run_image(also_wav=True))
        self._reg("buttons", b, "img_go_wav")
        b.pack(side="left")

        pv = ttk.LabelFrame(f, text=self.t("img_preview_frame"), padding=4)
        self._reg("frames", pv, "img_preview_frame")
        pv.pack(fill="both", expand=True, pady=(8, 0))
        self.i_canvas = tk.Canvas(pv, background="#f0f0f0", height=260,
                                  highlightthickness=0)
        self.i_canvas.pack(fill="both", expand=True)

        note = ttk.Label(f, text=self.t("img_note"),
                         foreground="#777", wraplength=740, justify="left")
        self._reg("labels", note, "img_note")
        note.pack(anchor="w")
        return f

    # ------------------------------------------------------------- 文件选择
    def _pick_image(self):
        p = filedialog.askopenfilename(
            title=self.t("fd_image"),
            filetypes=[(self.t("ft_image"),
                        "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"),
                       (self.t("ft_all"), "*")])
        if p:
            self.i_img.set(p)
            if not self.i_out.get():
                self.i_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_out3(self):
        p = filedialog.asksaveasfilename(title=self.t("fd_save_bas"), defaultextension=".bas",
                                         filetypes=[(self.t("ft_basic"), "*.bas")])
        if p:
            self.i_out.set(p)

    def _pick_wav_in(self):
        p = filedialog.askopenfilename(
            title=self.t("fd_wav_in"),
            filetypes=[(self.t("ft_audio"), "*.wav *.mp3 *.m4a"),
                       (self.t("ft_all"), "*")])
        if p:
            self.r_wav.set(p)
            if not self.r_out.get():
                self.r_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_in(self):
        p = filedialog.askopenfilename(
            title=self.t("fd_bas_in"),
            filetypes=[(self.t("ft_basic"), "*.bas *.BAS"), (self.t("ft_all"), "*")])
        if p:
            self.w_bas.set(p)
            if not self.w_out.get():
                self.w_out.set(os.path.splitext(p)[0] + ".wav")
            if not self.w_name.get():
                self.w_name.set(os.path.basename(os.path.splitext(p)[0])[:16])

    def _pick_bas_out2(self):
        p = filedialog.asksaveasfilename(title=self.t("fd_save_bas"), defaultextension=".bas",
                                         filetypes=[(self.t("ft_basic"), "*.bas")])
        if p:
            self.r_out.set(p)

    def _pick_wav_out(self):
        p = filedialog.asksaveasfilename(title=self.t("fd_save_wav"), defaultextension=".wav",
                                         filetypes=[(self.t("ft_wav"), "*.wav")])
        if p:
            self.w_out.set(p)

    # ----------------------------------------------------------------- 执行
    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy, msg_key=None):
        self.busy = busy
        for b in (self.md_btn_go, self.w_btn, self.r_btn,
                  self.i_btn_preview, self.i_btn_go):
            b.state(["disabled"] if busy else ["!disabled"])
        if busy:
            self.progress.start(12)
            self.status.configure(text=self.t(msg_key) if msg_key else self.t("status_busy"))
        else:
            self.progress.stop()
            self.status.configure(text=self.t(msg_key) if msg_key else self.t("status_ready"))

    def _run_cmd(self, argv, title):
        if self.busy:
            return
        self._append(self.t("log_section") % title)
        self._append(self.t("log_cmd_prefix") +
                     " ".join(shlex.quote(a) for a in argv) + "\n")
        self._set_busy(True, "status_running")

        def work():
            try:
                proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True,
                                        errors="replace", bufsize=1)
                for line in proc.stdout:
                    self.outq.put(("line", line))
                rc = proc.wait()
                self.outq.put(("done", (rc, title)))
            except Exception as e:      # noqa: BLE001
                self.outq.put(("line", self.t("log_start_failed") % e))
                self.outq.put(("done", (1, title)))

        threading.Thread(target=work, daemon=True).start()

    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.outq.get_nowait()
                if kind == "line":
                    self._append(payload)
                elif kind == "preview":
                    segs, pw, ph, err = payload
                    self._set_busy(False)
                    if err:
                        if err == "no-lines":
                            self._append(self.t("log_preview_err") + "\n")
                        else:
                            self._append(self.t("log_preview_failed") % err)
                        self.status.configure(text=self.t("status_preview_failed"))
                    else:
                        n = len(segs) if segs else 0
                        self._append(self.t("log_lines") % (n, pw, ph))
                        self._draw_preview(segs, pw, ph)
                        self.status.configure(text=self.t("status_preview_done") % n)
                elif kind == "done":
                    rc, title = payload
                    self._set_busy(False)
                    if rc == 0:
                        self._append(self.t("log_done") % title)
                        self.status.configure(text=self.t("status_done"))
                    else:
                        self._append(self.t("log_failed") % (title, rc))
                        self.status.configure(text=self.t("status_failed"))
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    # ------------------------------------------------------------- 各功能
    def _bas2wav_argv(self):
        src = self.w_bas.get().strip()
        if not src:
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_bas"))
            return None
        if not os.path.exists(src):
            messagebox.showerror(self.t("dlg_not_found"), src)
            return None
        out = self.w_out.get().strip() or (os.path.splitext(src)[0] + ".wav")
        argv = [BAS2WAV]
        name = self.w_name.get().strip()
        if name:
            argv += ["-n", name[:16]]
        sync = self.w_sync.get().strip()
        if sync:
            argv += ["-s", sync]
        rate = self.w_rate.get().strip()
        if rate:
            argv += ["-r", rate]
        argv += [src, out]
        return argv, out

    def _run_bas2wav(self):
        r = self._bas2wav_argv()
        if r:
            self._run_cmd(r[0], self.t("log_bas2wav"))

    def _run_bas2wav_and_play(self):
        r = self._bas2wav_argv()
        if not r:
            return
        argv, out = r

        def after_done():
            reader = shutil.which("ffplay") or shutil.which("aplay")
            if not reader:
                self._append(self.t("log_no_player"))
                return
            cmd = [reader, "-nodisp", "-autoexit", out] if "ffplay" in reader else [reader, out]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._run_cmd(argv, self.t("log_bas2wav"))
        self.after(1500, after_done)

    def _image_argv(self, out_path=None, preview=None):
        img = self.i_img.get().strip()
        if not img:
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_img"))
            return None
        if not os.path.exists(img):
            messagebox.showerror(self.t("dlg_not_found_img"), img)
            return None
        out = out_path or self.i_out.get().strip() or (os.path.splitext(img)[0] + ".bas")

        argv = [PY, IMG2LINES, img, out,
                "--mode", self.i_mode.get() or "edge",
                "--threshold", (self.i_thr.get() or "128").strip(),
                "--max-side", (self.i_side.get() or "420").strip(),
                "--simplify", (self.i_simpl.get() or "1.0").strip()]
        if self.i_invert.get():
            argv += ["--invert"]
        if preview:
            argv += ["--preview", preview]
        return argv, out

    def _preview_image(self):
        img = self.i_img.get().strip()
        if not img or not os.path.exists(img):
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_img"))
            return
        if self.busy:
            return
        self._set_busy(True, "status_previewing")
        self._append(self.t("log_section") % self.t("log_preview"))

        params = {
            "mode": self.i_mode.get() or "edge",
            "threshold": int(self.i_thr.get() or 128),
            "max_side": int(self.i_side.get() or 420),
            "simplify": float(self.i_simpl.get() or 1.0),
            "invert": bool(self.i_invert.get()),
        }

        def work():
            try:
                segs, pw, ph, err = preview_lines(img, params)
                self.outq.put(("preview", (segs, pw, ph, err)))
            except Exception as e:  # noqa: BLE001
                self.outq.put(("preview", (None, 0, 0, str(e))))

        threading.Thread(target=work, daemon=True).start()

    def _draw_preview(self, segs, pw, ph):
        """Preview at the real CE-150 paper size (pw/ph = X_MAX × Y_MAX, in steps)."""
        c = self.i_canvas
        c.delete("all")
        if pw <= 0 or ph <= 0:
            return

        cw = max(c.winfo_width(), 200)
        ch = max(c.winfo_height(), 150)
        margin = 10
        avail_w = cw - 2 * margin
        avail_h = ch - 2 * margin

        scale = min(avail_w / float(pw), avail_h / float(ph))
        ox = margin + (avail_w - pw * scale) / 2.0
        oy = margin + (avail_h - ph * scale) / 2.0

        c.create_rectangle(ox, oy, ox + pw * scale, oy + ph * scale,
                           fill="#fdfdf5", outline="#bbb")

        grid = 50
        for gx in range(grid, int(pw), grid):
            x = ox + gx * scale
            c.create_line(x, oy, x, oy + ph * scale, fill="#eee")
        for gy in range(grid, int(ph), grid):
            y = oy + gy * scale
            c.create_line(ox, y, ox + pw * scale, y, fill="#eee")

        for (x0, y0, x1, y1) in segs:
            c.create_line(
                ox + x0 * scale, oy + ph * scale - y0 * scale,
                ox + x1 * scale, oy + ph * scale - y1 * scale,
                fill="black", width=1)

        c.create_text(cw - 6, ch - 6, anchor="se",
                      text=self.t("canvas_info") % (pw, ph, len(segs), pw * 0.2, ph * 0.2),
                      fill="#888")

    def _run_image(self, also_wav=False):
        r = self._image_argv()
        if not r:
            return
        argv, out = r
        self._run_cmd(argv, self.t("log_img2bas"))
        if also_wav:
            wav = os.path.splitext(out)[0] + ".wav"
            name = os.path.splitext(os.path.basename(out))[0][:16]
            self.after(600, lambda: self._run_cmd(
                [BAS2WAV, "-n", name, "-r", "48k", out, wav],
                self.t("log_img2wav")))

    def _run_wav2bas(self, also_img=False):
        src = self.r_wav.get().strip()
        if not src:
            messagebox.showwarning(self.t("dlg_missing_in"), self.t("dlg_missing_in_wav"))
            return
        if not os.path.exists(src):
            messagebox.showerror(self.t("dlg_not_found"), src)
            return
        out = self.r_out.get().strip() or (os.path.splitext(src)[0] + ".bas")
        argv = [WAV2BAS]
        dev = self.r_dev.get().strip()
        if dev and dev not in ("自动", "Auto"):
            argv += ["-d", dev]
        if also_img:
            argv += ["-i", os.path.splitext(out)[0] + ".img"]
        argv += [src, out]
        self._run_cmd(argv, self.t("log_wav2bas"))


if __name__ == "__main__":
    App().mainloop()
