#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc1500ui.py —— PC-1500 音频/BASIC 转换的图形界面（tkinter，无第三方依赖）

功能:
  1. MIDI -> BEEP 音乐 BASIC      （调 midi2beep_pc1500.py）
  2. BASIC -> 磁带 WAV            （调 bas2wav / bin2wav）
  3. 磁带 WAV -> BASIC            （调 wav2bas / wav2bin）
  4. 图片 -> CE-150 绘图 BASIC     （调 img2lines.py）

启动:  ./pc1500ui.py
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


def preview_lines(img_path, params):
    """用 img2lines.py 的函数算出线条预览。

    返回 (segs, paper_w, paper_h, err)：
        segs 坐标在纸带 [0, paper_w] × [0, paper_h] 内（Y 已翻转）。
    """
    if not os.path.exists(IMG2LINES):
        return None, 0, 0, "找不到 img2lines.py（%s）" % IMG2LINES
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("img2lines", IMG2LINES)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        return None, 0, 0, "加载 img2lines.py 失败: %s" % e

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
            return None, 0, 0, "没有提取到线条，试试调低阈值或换成 mono 模式"

        segs, pw, ph = mod.map_to_plot(segs, w, h, plot_w, plot_h, True)
        return segs, pw, ph, None
    except SystemExit as e:
        return None, 0, 0, "img2lines 退出: %s" % (e.code if e.code else e)
    except Exception as e:  # noqa: BLE001
        return None, 0, 0, "preview_lines() 出错: %s" % e


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PC-1500 音频 / BASIC 转换工具")
        self.geometry("820x640")
        self.minsize(720, 560)

        self.outq = queue.Queue()
        self.busy = False

        self._build_ui()
        self.after(100, self._drain_queue)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self, padding=(12, 10, 12, 4))
        header.pack(fill="x")
        ttk.Label(header, text="PC-1500 音频 / BASIC 转换工具",
                  font=("", 14, "bold")).pack(anchor="w")
        ttk.Label(header,
                  text="MIDI → BEEP 音乐，BASIC ↔ 磁带音频，图片 → CE-150 绘图",
                  foreground="#555").pack(anchor="w")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=12, pady=6)

        self._tab_midi = self._build_midi_tab(nb)
        nb.add(self._tab_midi, text="  MIDI → BEEP 音乐  ")

        self._tab_to_wav = self._build_bas2wav_tab(nb)
        nb.add(self._tab_to_wav, text="  BASIC → 磁带 WAV  ")

        self._tab_from_wav = self._build_wav2bas_tab(nb)
        nb.add(self._tab_from_wav, text="  磁带 WAV → BASIC  ")

        self._tab_img = self._build_image_tab(nb)
        nb.add(self._tab_img, text="  图片 → 打印机绘图  ")

        logf = ttk.LabelFrame(self, text="输出", padding=6)
        logf.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        self.log = tk.Text(logf, height=8, wrap="word", state="disabled",
                           font=("monospace", 9), background="#f8f8f8")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(self, padding=(12, 2, 12, 8))
        bar.pack(fill="x")
        self.status = ttk.Label(bar, text="就绪")
        self.status.pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=160)
        self.progress.pack(side="right")

    def _row(self, parent, label, var, cmd, width=58):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=10).pack(side="left")
        e = ttk.Entry(f, textvariable=var, width=width)
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(f, text="浏览…", command=cmd).pack(side="left")
        return e

    # ---------------------------------------------------------- MIDI → BEEP
    def _build_midi_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.md_midi = tk.StringVar()
        self.md_out = tk.StringVar()

        ttk.Label(f, text="把 MIDI 文件转成 PC-1500 的 BEEP 音乐 BASIC。"
                          "多轨文件默认自动选主旋律轨，也可以手动指定。",
                  foreground="#444").pack(anchor="w", pady=(0, 8))

        self._row(f, "MIDI 文件", self.md_midi, self._pick_midi)
        self._row(f, "输出 .bas", self.md_out, self._pick_bas_out_midi)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        ttk.Label(opt, text="轨道").pack(side="left")
        self.md_track = tk.StringVar(value="自动")
        self.md_track_combo = ttk.Combobox(opt, textvariable=self.md_track,
                                           state="normal", width=8,
                                           values=["自动"])
        self.md_track_combo.pack(side="left", padx=(4, 14))
        ttk.Button(opt, text="列出轨道", command=self._list_midi_tracks).pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.md_btn_go = ttk.Button(btns, text="生成 BASIC", command=self._run_midi)
        self.md_btn_go.pack(side="left")

        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Label(f, text="说明：蜂鸣器只能单音，和弦只保留最高音。频率参数映射到"
                          "PC-1500 上已验证可用的 143–245 区间，超出范围的音符会被"
                          "钳制到边界。生成后用「BASIC → 磁带 WAV」转成音频再 CLOAD。",
                  foreground="#777", wraplength=740, justify="left").pack(anchor="w")
        return f

    def _pick_midi(self):
        p = filedialog.askopenfilename(
            title="选择 MIDI",
            filetypes=[("MIDI", "*.mid *.midi"), ("所有文件", "*")])
        if p:
            self.md_midi.set(p)
            if not self.md_out.get():
                self.md_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_out_midi(self):
        p = filedialog.asksaveasfilename(title="保存 BASIC 为", defaultextension=".bas",
                                         filetypes=[("BASIC", "*.bas")])
        if p:
            self.md_out.set(p)

    def _midi_argv(self):
        src = self.md_midi.get().strip()
        if not src:
            messagebox.showwarning("缺少输入", "先选一个 MIDI 文件。")
            return None
        if not os.path.exists(src):
            messagebox.showerror("找不到文件", src)
            return None
        out = self.md_out.get().strip() or (os.path.splitext(src)[0] + ".bas")
        argv = [PY, MIDI2BEEP, src, out]
        tr = self.md_track.get().strip()
        if tr and tr != "自动":
            argv += ["--track", tr]
        return argv, out

    def _run_midi(self):
        r = self._midi_argv()
        if r:
            self._run_cmd(r[0], "MIDI → BEEP BASIC")

    def _list_midi_tracks(self):
        src = self.md_midi.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showwarning("缺少输入", "先选一个 MIDI 文件。")
            return
        self._run_cmd([PY, MIDI2BEEP, "--list-tracks", src], "列出 MIDI 轨道")

    # ---------------------------------------------------------- BASIC → WAV
    def _build_bas2wav_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.w_bas = tk.StringVar()
        self.w_out = tk.StringVar()

        ttk.Label(f, text="把 BASIC 程序编成磁带音频，用 CE-150 的 EAR 口放给 PC-1500 的 CLOAD 听。",
                  foreground="#444").pack(anchor="w", pady=(0, 8))
        self._row(f, "BASIC", self.w_bas, self._pick_bas_in)
        self._row(f, "输出 .wav", self.w_out, self._pick_wav_out)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        ttk.Label(opt, text="保存名").pack(side="left")
        self.w_name = tk.StringVar()
        ttk.Entry(opt, textvariable=self.w_name, width=18).pack(side="left", padx=(4, 14))
        ttk.Label(opt, text="同步").pack(side="left")
        self.w_sync = tk.StringVar(value="2.0")
        ttk.Entry(opt, textvariable=self.w_sync, width=6).pack(side="left", padx=(4, 2))
        ttk.Label(opt, text="秒").pack(side="left", padx=(0, 10))
        ttk.Label(opt, text="采样率").pack(side="left")
        self.w_rate = tk.StringVar(value="48k")
        ttk.Combobox(opt, textvariable=self.w_rate, state="readonly", width=6,
                     values=["48k", "16k", "44k", "10k"]).pack(side="left", padx=(4, 4))

        ttk.Label(f, text="保存名 = 真机上 CLOAD \"名字\" 用的名字（最多 16 字符）；"
                          "采样率 48k 最稳，读不出时依次试 48k / 16k / 44k。",
                  foreground="#666", wraplength=740, justify="left").pack(anchor="w", pady=(6, 0))

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.w_btn = ttk.Button(btns, text="生成 WAV", command=self._run_bas2wav)
        self.w_btn.pack(side="left")
        ttk.Button(btns, text="生成后播放", command=self._run_bas2wav_and_play).pack(side="left", padx=6)
        return f

    # ---------------------------------------------------------- WAV → BASIC
    def _build_wav2bas_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.r_wav = tk.StringVar()
        self.r_out = tk.StringVar()

        ttk.Label(f, text="把 PC-1500 用 CSAVE 录出来的音频还原成 BASIC 源码。",
                  foreground="#444").pack(anchor="w", pady=(0, 8))
        self._row(f, "录音文件", self.r_wav, self._pick_wav_in)
        self._row(f, "输出 .bas", self.r_out, self._pick_bas_out2)

        opt = ttk.Frame(f)
        opt.pack(fill="x", pady=(8, 4))
        ttk.Label(opt, text="录音来源").pack(side="left")
        self.r_dev = tk.StringVar(value="自动")
        ttk.Combobox(opt, textvariable=self.r_dev, state="readonly", width=8,
                     values=["自动", "CAS", "AIR", "EMU"]).pack(side="left", padx=(4, 14))
        ttk.Label(opt, text="（磁带机直录用 CAS；蜂鸣器外录用 AIR；模拟器录的音用 EMU）",
                  foreground="#666").pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.r_btn = ttk.Button(btns, text="还原成 BASIC", command=self._run_wav2bas)
        self.r_btn.pack(side="left")
        ttk.Button(btns, text="同时导出中间码 .img",
                   command=lambda: self._run_wav2bas(also_img=True)).pack(side="left", padx=6)

        ttk.Separator(f).pack(fill="x", pady=10)
        ttk.Label(f, text="录音要求：采样率至少 11025 Hz，单声道，尽量 16-bit，"
                          "幅度接近但别过载，别剪掉开头的引导音。",
                  foreground="#777", wraplength=740, justify="left").pack(anchor="w")
        return f

    # ---------------------------------------------------------- 图片 → 绘图
    def _build_image_tab(self, nb):
        f = ttk.Frame(nb, padding=10)
        self.i_img = tk.StringVar()
        self.i_out = tk.StringVar()

        ttk.Label(f, text="把图片变成线条画，生成 CE-150 打印机能画的 BASIC 程序。",
                  foreground="#444").pack(anchor="w", pady=(0, 8))

        self._row(f, "图片", self.i_img, self._pick_image)
        self._row(f, "输出 .bas", self.i_out, self._pick_bas_out3)

        r1 = ttk.Frame(f)
        r1.pack(fill="x", pady=(8, 3))
        ttk.Label(r1, text="模式").pack(side="left")
        self.i_mode = tk.StringVar(value="edge")
        ttk.Combobox(r1, textvariable=self.i_mode, state="readonly", width=6,
                     values=["edge", "mono"]).pack(side="left", padx=(4, 4))
        ttk.Label(r1, text="（edge=照片边缘 / mono=线稿深色部分）",
                  foreground="#666").pack(side="left", padx=(0, 14))
        ttk.Label(r1, text="阈值").pack(side="left")
        self.i_thr = tk.StringVar(value="128")
        ttk.Spinbox(r1, textvariable=self.i_thr, from_=10, to=250, width=5,
                    increment=10).pack(side="left", padx=(4, 2))
        self.i_invert = tk.BooleanVar(value=False)
        ttk.Checkbutton(r1, text="反色", variable=self.i_invert).pack(side="left", padx=(10, 0))

        r2 = ttk.Frame(f)
        r2.pack(fill="x", pady=3)
        ttk.Label(r2, text="细节").pack(side="left")
        self.i_side = tk.StringVar(value="420")
        ttk.Spinbox(r2, textvariable=self.i_side, from_=80, to=900, width=5,
                    increment=20).pack(side="left", padx=(4, 2))
        ttk.Label(r2, text="（数值越大线越多越细，程序也越长）",
                  foreground="#666").pack(side="left")

        r3 = ttk.Frame(f)
        r3.pack(fill="x", pady=3)
        ttk.Label(r3, text="抽稀").pack(side="left")
        self.i_simpl = tk.StringVar(value="1.0")
        ttk.Spinbox(r3, textvariable=self.i_simpl, from_=0.3, to=5.0, width=5,
                    increment=0.2).pack(side="left", padx=(4, 2))
        ttk.Label(r3, text="（越大线越少；程序太长时调大）",
                  foreground="#666").pack(side="left")

        btns = ttk.Frame(f)
        btns.pack(fill="x", pady=(10, 0))
        self.i_btn_preview = ttk.Button(btns, text="① 预览线条", command=self._preview_image)
        self.i_btn_preview.pack(side="left")
        self.i_btn_go = ttk.Button(btns, text="② 生成 BASIC", command=self._run_image)
        self.i_btn_go.pack(side="left", padx=6)
        ttk.Button(btns, text="生成并转 WAV",
                   command=lambda: self._run_image(also_wav=True)).pack(side="left")

        pv = ttk.LabelFrame(f, text="预览（按 CE-150 真实纸带比例）", padding=4)
        pv.pack(fill="both", expand=True, pady=(8, 0))
        self.i_canvas = tk.Canvas(pv, background="#f0f0f0", height=260,
                                  highlightthickness=0)
        self.i_canvas.pack(fill="both", expand=True)

        ttk.Label(f, text="CE-150 有效绘图区：横向约 216 步（43.2mm），纵向约 512 步"
                          "（102.4mm），每步 0.2mm。预览里的纸带和留白就是实机效果。",
                  foreground="#777", wraplength=740, justify="left").pack(anchor="w")
        return f

    # ------------------------------------------------------------- 文件选择
    def _pick_image(self):
        p = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff"),
                       ("所有文件", "*")])
        if p:
            self.i_img.set(p)
            if not self.i_out.get():
                self.i_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_out3(self):
        p = filedialog.asksaveasfilename(title="保存 BASIC 为", defaultextension=".bas",
                                         filetypes=[("BASIC", "*.bas")])
        if p:
            self.i_out.set(p)

    def _pick_wav_in(self):
        p = filedialog.askopenfilename(title="选择录音",
                                       filetypes=[("音频", "*.wav *.mp3 *.m4a"), ("所有文件", "*")])
        if p:
            self.r_wav.set(p)
            if not self.r_out.get():
                self.r_out.set(os.path.splitext(p)[0] + ".bas")

    def _pick_bas_in(self):
        p = filedialog.askopenfilename(title="选择 BASIC 源文件",
                                       filetypes=[("BASIC", "*.bas *.BAS"), ("所有文件", "*")])
        if p:
            self.w_bas.set(p)
            if not self.w_out.get():
                self.w_out.set(os.path.splitext(p)[0] + ".wav")
            if not self.w_name.get():
                self.w_name.set(os.path.basename(os.path.splitext(p)[0])[:16])

    def _pick_bas_out2(self):
        p = filedialog.asksaveasfilename(title="保存 BASIC 为", defaultextension=".bas",
                                         filetypes=[("BASIC", "*.bas")])
        if p:
            self.r_out.set(p)

    def _pick_wav_out(self):
        p = filedialog.asksaveasfilename(title="保存 WAV 为", defaultextension=".wav",
                                         filetypes=[("WAV", "*.wav")])
        if p:
            self.w_out.set(p)

    # ----------------------------------------------------------------- 执行
    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy, msg=""):
        self.busy = busy
        for b in (self.md_btn_go, self.w_btn, self.r_btn,
                  self.i_btn_preview, self.i_btn_go):
            b.state(["disabled"] if busy else ["!disabled"])
        if busy:
            self.progress.start(12)
            self.status.configure(text=msg or "处理中…")
        else:
            self.progress.stop()
            self.status.configure(text=msg or "就绪")

    def _run_cmd(self, argv, title):
        if self.busy:
            return
        self._append("\n=== %s ===\n" % title)
        self._append("$ " + " ".join(shlex.quote(a) for a in argv) + "\n")
        self._set_busy(True, "运行中…")

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
                self.outq.put(("line", "启动失败: %s\n" % e))
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
                        self._append("预览失败: %s\n" % err)
                        self.status.configure(text="预览失败")
                    else:
                        n = len(segs) if segs else 0
                        self._append("线条 %d 条，纸带 %d x %d 步\n" % (n, pw, ph))
                        self._draw_preview(segs, pw, ph)
                        self.status.configure(text="预览完成（%d 条线）" % n)
                elif kind == "done":
                    rc, title = payload
                    self._set_busy(False)
                    if rc == 0:
                        self._append("\n[完成] %s\n" % title)
                        self.status.configure(text="完成")
                    else:
                        self._append("\n[失败] %s，返回码 %d\n" % (title, rc))
                        self.status.configure(text="失败")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    # ------------------------------------------------------------- 各功能
    def _bas2wav_argv(self):
        src = self.w_bas.get().strip()
        if not src:
            messagebox.showwarning("缺少输入", "先选一个 BASIC 文件。")
            return None
        if not os.path.exists(src):
            messagebox.showerror("找不到文件", src)
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
            self._run_cmd(r[0], "BASIC → WAV")

    def _run_bas2wav_and_play(self):
        r = self._bas2wav_argv()
        if not r:
            return
        argv, out = r

        def after_done():
            reader = shutil.which("ffplay") or shutil.which("aplay")
            if not reader:
                self._append("没找到 ffplay/aplay，无法自动播放，请手动打开文件。\n")
                return
            cmd = [reader, "-nodisp", "-autoexit", out] if "ffplay" in reader else [reader, out]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._run_cmd(argv, "BASIC → WAV")
        self.after(1500, after_done)

    def _image_argv(self, out_path=None, preview=None):
        img = self.i_img.get().strip()
        if not img:
            messagebox.showwarning("缺少输入", "先选一张图片。")
            return None
        if not os.path.exists(img):
            messagebox.showerror("找不到图片", img)
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
            messagebox.showwarning("缺少输入", "先选一张图片。")
            return
        if self.busy:
            return
        self._set_busy(True, "预览中…")
        self._append("\n=== 预览线条 ===\n")

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
        """按 CE-150 真实纸带尺寸预览（pw/ph = X_MAX × Y_MAX，单位步）。"""
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
                      text="纸带 %d×%d 步 / %d 条线 (%.1f×%.1f mm)"
                           % (pw, ph, len(segs), pw * 0.2, ph * 0.2),
                      fill="#888")

    def _run_image(self, also_wav=False):
        r = self._image_argv()
        if not r:
            return
        argv, out = r
        self._run_cmd(argv, "图片 → 绘图 BASIC")
        if also_wav:
            wav = os.path.splitext(out)[0] + ".wav"
            name = os.path.splitext(os.path.basename(out))[0][:16]
            self.after(600, lambda: self._run_cmd(
                [BAS2WAV, "-n", name, "-r", "48k", out, wav],
                "绘图 BASIC → WAV"))

    def _run_wav2bas(self, also_img=False):
        src = self.r_wav.get().strip()
        if not src:
            messagebox.showwarning("缺少输入", "先选一个录音文件。")
            return
        if not os.path.exists(src):
            messagebox.showerror("找不到文件", src)
            return
        out = self.r_out.get().strip() or (os.path.splitext(src)[0] + ".bas")
        argv = [WAV2BAS]
        dev = self.r_dev.get().strip()
        if dev and dev != "自动":
            argv += ["-d", dev]
        if also_img:
            argv += ["-i", os.path.splitext(out)[0] + ".img"]
        argv += [src, out]
        self._run_cmd(argv, "WAV → BASIC")


if __name__ == "__main__":
    App().mainloop()
