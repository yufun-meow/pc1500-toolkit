#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
img2lines.py —— 把图片转成线条，再生成 PC-1500 + CE-150 打印机的绘图 BASIC 程序

CE-150 物理规格:
    每步 0.2mm
    横向有效行程约 43.2mm  ->  216 步
    纵向有效行程约 102.4mm ->  512 步

用法:
    ./img2lines.py 照片.jpg
    ./img2lines.py --mode mono --invert 线稿.png   # 黑底白线时加 --invert
    ./img2lines.py --simplify 1.5 图片.jpg
"""

import argparse
import os
import shutil
import subprocess
import sys

# ---------------------------------------------------------------- 常量
MM_PER_UNIT = 0.2
X_MAX = 216
Y_MAX = 512
PAPER_MM = 57.0


# ---------------------------------------------------------------- 图像读取
def read_gray(path, max_side=600):
    """用 ImageMagick 读成灰度二维数组。返回 (宽, 高, [[0..255]...])。"""
    magick = shutil.which("magick") or shutil.which("convert")
    if not magick:
        sys.exit("需要 ImageMagick（magick 或 convert）来读图，请先安装。")
    if not os.path.exists(path):
        sys.exit("找不到图片: %s" % path)

    cmd = [magick, path, "-colorspace", "Gray",
           "-resize", "%dx%d>" % (max_side, max_side),
           "-depth", "8", "gray:-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        sys.exit("读图失败:\n" + proc.stderr.decode("utf-8", "replace"))

    sz = subprocess.run([magick, path, "-format", "%w %h", "info:"],
                        capture_output=True, text=True)
    w0, h0 = [int(x) for x in sz.stdout.split()]
    scale = min(1.0, float(max_side) / max(w0, h0))
    w, h = max(1, int(w0 * scale)), max(1, int(h0 * scale))

    data = proc.stdout
    if len(data) < w * h:
        for try_w in range(w, 0, -1):
            if len(data) % try_w == 0:
                w = try_w
                h = len(data) // w
                break
        else:
            sys.exit("图像数据长度异常: %d 字节" % len(data))

    px = [[data[y * w + x] for x in range(w)] for y in range(h)]
    return w, h, px


# ---------------------------------------------------------------- 线条化
def to_binary(w, h, px, mode, threshold=128, blur=1, invert=False):
    """生成 0/1 线条掩码。mode=edge 走边缘检测，mono 直接阈值。"""
    if blur > 0:
        px = box_blur(px, w, h, blur)

    if mode == "mono":
        if invert:
            return [[1 if px[y][x] > threshold else 0 for x in range(w)] for y in range(h)]
        return [[1 if px[y][x] < threshold else 0 for x in range(w)] for y in range(h)]

    # ---- edge: Sobel 梯度 + 双阈值滞后 ----
    grad = [[0] * w for _ in range(h)]
    vals = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            gx = (px[y - 1][x + 1] + 2 * px[y][x + 1] + px[y + 1][x + 1]
                  - px[y - 1][x - 1] - 2 * px[y][x - 1] - px[y + 1][x - 1])
            gy = (px[y + 1][x - 1] + 2 * px[y + 1][x] + px[y + 1][x + 1]
                  - px[y - 1][x - 1] - 2 * px[y - 1][x] - px[y - 1][x + 1])
            g = abs(gx) + abs(gy)
            grad[y][x] = g
            if g > 0:
                vals.append(g)

    if not vals:
        return [[0] * w for _ in range(h)]

    vals.sort()
    density = max(0.02, min(0.45, threshold / 128.0 * 0.10))
    hi_idx = int((1.0 - density) * (len(vals) - 1))
    thr_hi = max(2, vals[hi_idx])
    thr_lo = max(1, int(thr_hi * 0.4))

    strong = [[grad[y][x] >= thr_hi for x in range(w)] for y in range(h)]
    weak = [[thr_lo <= grad[y][x] < thr_hi for x in range(w)] for y in range(h)]

    out = [[1 if strong[y][x] else 0 for x in range(w)] for y in range(h)]
    stack = [(x, y) for y in range(h) for x in range(w) if strong[y][x]]
    while stack:
        x, y = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and weak[ny][nx] and not out[ny][nx]:
                    out[ny][nx] = 1
                    stack.append((nx, ny))
    return out


def box_blur(px, w, h, r):
    tmp = [[0] * w for _ in range(h)]
    for y in range(h):
        row = px[y]
        for x in range(w):
            s, n = 0, 0
            for dx in range(-r, r + 1):
                xx = x + dx
                if 0 <= xx < w:
                    s += row[xx]
                    n += 1
            tmp[y][x] = s // n
    out = [[0] * w for _ in range(h)]
    for x in range(w):
        for y in range(h):
            s, n = 0, 0
            for dy in range(-r, r + 1):
                yy = y + dy
                if 0 <= yy < h:
                    s += tmp[yy][x]
                    n += 1
            out[y][x] = s // n
    return out


def dilate(mask, w, h, r=1):
    out = [row[:] for row in mask]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w:
                        out[yy][xx] = 1
    return out


def thin(mask, w, h):
    """细化（Zhang-Suen）。"""
    img = [row[:] for row in mask]
    changed = True
    guard = 0
    while changed and guard < 60:
        changed = False
        guard += 1
        for step in (0, 1):
            rm = []
            for y in range(1, h - 1):
                for x in range(1, w - 1):
                    if not img[y][x]:
                        continue
                    p2 = img[y - 1][x]
                    p3 = img[y - 1][x + 1]
                    p4 = img[y][x + 1]
                    p5 = img[y + 1][x + 1]
                    p6 = img[y + 1][x]
                    p7 = img[y + 1][x - 1]
                    p8 = img[y][x - 1]
                    p9 = img[y - 1][x - 1]
                    nb = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                    if nb < 2 or nb > 6:
                        continue
                    seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
                    trans = sum(1 for i in range(8) if seq[i] == 0 and seq[i + 1] == 1)
                    if trans != 1:
                        continue
                    if step == 0:
                        if p2 * p4 * p6 != 0 or p4 * p6 * p8 != 0:
                            continue
                    else:
                        if p2 * p4 * p8 != 0 or p2 * p6 * p8 != 0:
                            continue
                    rm.append((y, x))
            if rm:
                changed = True
                for y, x in rm:
                    img[y][x] = 0
    return img


def to_segments(mask, w, h, simplify=1.0):
    """线条追踪。先消 2x2 冗余块，再用无向边去重，避免重复路径。"""
    pts = set()
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if row[x]:
                pts.add((x, y))
    if not pts:
        return []

    # 消 2x2 块里多余的点
    changed = True
    while changed:
        changed = False
        rm = []
        for (x, y) in pts:
            if ((x + 1, y) in pts and (x, y + 1) in pts and (x + 1, y + 1) in pts):
                rm.append((x + 1, y + 1))
        if rm:
            changed = True
            for p in rm:
                pts.discard(p)

    def _redundant(a, b):
        ax, ay = a
        bx, by = b
        if abs(ax - bx) != 1 or abs(ay - by) != 1:
            return False
        return ((ax, by) in pts) or ((bx, ay) in pts)

    def _endpoints(pset):
        eps = []
        for (x, y) in pset:
            cnt = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    if (x + dx, y + dy) in pset:
                        cnt += 1
            if cnt == 1:
                eps.append((x, y))
        return eps

    eps = _endpoints(pts)
    for (x, y) in eps:
        if (x, y) not in pts:
            continue
        best, bd = None, 999
        for (x2, y2) in eps:
            if (x2, y2) == (x, y) or (x2, y2) not in pts:
                continue
            d = max(abs(x2 - x), abs(y2 - y))
            if 0 < d <= 2 and d < bd:
                bd, best = d, (x2, y2)
        if best is None:
            continue
        x2, y2 = best
        steps = max(abs(x2 - x), abs(y2 - y))
        for t in range(1, steps):
            xx = int(round(x + (x2 - x) * t / float(steps)))
            yy = int(round(y + (y2 - y) * t / float(steps)))
            pts.add((xx, yy))

    def nbrs(p):
        x, y = p
        out = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                q = (x + dx, y + dy)
                if q in pts and not _redundant(p, q):
                    out.append(q)
        return out

    deg = {p: len(nbrs(p)) for p in pts}
    nodes = {p for p in pts if deg[p] != 2}
    visited_undirected = set()
    paths = []

    def _key(a, b):
        return (a, b) if a <= b else (b, a)

    def walk(start, nxt):
        path = [start, nxt]
        visited_undirected.add(_key(start, nxt))
        cur, prev = nxt, start
        while cur not in nodes:
            cand = [q for q in nbrs(cur) if q != prev]
            if not cand:
                break
            nxt2 = None
            for q in cand:
                if _key(cur, q) not in visited_undirected:
                    nxt2 = q
                    break
            if nxt2 is None:
                break
            visited_undirected.add(_key(cur, nxt2))
            path.append(nxt2)
            prev, cur = cur, nxt2
        return path

    for nd in nodes:
        for nb in nbrs(nd):
            if _key(nd, nb) in visited_undirected:
                continue
            paths.append(walk(nd, nb))

    for p in pts:
        if deg[p] != 2:
            continue
        for nb in nbrs(p):
            if _key(p, nb) in visited_undirected:
                continue
            path = walk(p, nb)
            if len(path) > 3:
                paths.append(path)

    out = []
    eps_r = max(0.8, simplify * 1.2)
    min_path = max(3, int(round(simplify * 3)))
    for path in paths:
        if len(path) < min_path:
            continue
        simp = rdp([(float(x), float(y)) for (x, y) in path], eps_r)
        for k in range(len(simp) - 1):
            x0, y0 = simp[k]
            x1, y1 = simp[k + 1]
            if x0 == x1 and y0 == y1:
                continue
            out.append((x0, y0, x1, y1))
    return out


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = (dx * dx + dy * dy) ** 0.5
    best_i, best_d = 0, -1.0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if norm == 0:
            d = ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
        else:
            d = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / norm
        if d > best_d:
            best_d, best_i = d, i
    if best_d > eps:
        left = rdp(pts[:best_i + 1], eps)
        right = rdp(pts[best_i:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]


# ---------------------------------------------------------------- 坐标映射
def map_to_plot(segs, w, h, plot_w=None, plot_h=None,
                flip_y=True, center=True, clamp=True):
    """像素坐标 -> CE-150 绘图坐标。返回 (segs, paper_w, paper_h)。"""
    x_cap = X_MAX if plot_w is None else min(int(plot_w), X_MAX)
    y_cap = Y_MAX if plot_h is None else min(int(plot_h), Y_MAX)

    if not segs:
        return [], x_cap, y_cap

    xs = [p[0] for s in segs for p in ((s[0], s[1]), (s[2], s[3]))]
    ys = [p[1] for s in segs for p in ((s[0], s[1]), (s[2], s[3]))]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    src_w = max(1.0, x1 - x0)
    src_h = max(1.0, y1 - y0)

    scale = x_cap / src_w
    if src_h * scale > y_cap:
        scale = y_cap / src_h

    draw_w = src_w * scale
    draw_h = src_h * scale

    off_x = (x_cap - draw_w) / 2.0 if center else 0.0
    off_y = (y_cap - draw_h) / 2.0 if center else 0.0

    out = []
    for (px0, py0, px1, py1) in segs:
        nx0 = (px0 - x0) * scale + off_x
        nx1 = (px1 - x0) * scale + off_x
        ny0 = (py0 - y0) * scale + off_y
        ny1 = (py1 - y0) * scale + off_y
        if flip_y:
            ny0 = y_cap - ny0
            ny1 = y_cap - ny1
        if clamp:
            nx0 = max(0.0, min(float(x_cap), nx0))
            nx1 = max(0.0, min(float(x_cap), nx1))
            ny0 = max(0.0, min(float(y_cap), ny0))
            ny1 = max(0.0, min(float(y_cap), ny1))
        if abs(nx1 - nx0) < 0.5 and abs(ny1 - ny0) < 0.5:
            continue
        out.append((nx0, ny0, nx1, ny1))
    return out, x_cap, y_cap


# ---------------------------------------------------------------- 预览
def export_preview(segs, plot_w, plot_h, path):
    if not segs:
        return None
    body = "".join(
        '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
        % (x0, plot_h - y0, x1, plot_h - y1)
        for (x0, y0, x1, y1) in segs)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
           '<rect width="100%%" height="100%%" fill="white"/>'
           '<g stroke="black" stroke-width="1" stroke-linecap="round">%s</g></svg>'
           % (plot_w + 2, plot_h + 2, body))
    with open(path, "w", encoding="ascii") as f:
        f.write(svg)
    return path


# ---------------------------------------------------------------- 生成 BASIC
def chunk_lines(segs, width, max_line_items=6):
    """退化线段（舍入后两端重合）直接丢弃。"""
    stmts = []
    for (x0, y0, x1, y1) in segs:
        ix0, iy0 = int(round(x0)), int(round(y0))
        ix1, iy1 = int(round(x1)), int(round(y1))
        if ix0 == ix1 and iy0 == iy1:
            continue
        stmts.append("LINE (%d,%d)-(%d,%d)" % (ix0, iy0, ix1, iy1))
    return stmts


def emit_basic(stmts, plot_w, plot_h, title="", step=10, max_chars=78):
    out = []
    n = step

    def add(text):
        nonlocal n
        out.append((n, text))
        n += step

    safe = "".join(c for c in title if c.isalnum() or c in " _.-+/")[:36]
    add("REM PC-1500 CE-150 DRAWING")
    if safe:
        add("REM %s" % safe)
    add("GRAPH")
    add("GLCURSOR (0,0)")
    buf = ""
    for s in stmts:
        cand = s if not buf else buf + ":" + s
        if len(cand) > max_chars:
            add(buf)
            buf = s
        else:
            buf = cand
    if buf:
        add(buf)

    add("TEXT")
    add("END")
    return "".join("%d %s\r\n" % (ln, tx) for ln, tx in out)


# ---------------------------------------------------------------- 主程序
def main(argv):
    ap = argparse.ArgumentParser(
        description="图片 -> 线条 -> PC-1500 CE-150 绘图 BASIC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="生成的 .bas 用同目录 ./bas2wav 变成磁带音频，机器上 CLOAD 就能画。")
    ap.add_argument("image", help="输入图片")
    ap.add_argument("output", nargs="?", help="输出 .bas")
    ap.add_argument("--mode", choices=["edge", "mono"], default="edge",
                    help="edge=边缘检测（照片，默认）；mono=深色像素当线（线稿）")
    ap.add_argument("--invert", action="store_true",
                    help="mono 模式下反色（黑底白线时用）")
    ap.add_argument("--paper-mm", type=float, default=PAPER_MM,
                    help="纸宽毫米，仅记录（默认 57）")
    ap.add_argument("--mm-per-unit", type=float, default=MM_PER_UNIT,
                    help="每绘图单位毫米数（默认 0.2，一般不用改）")
    ap.add_argument("--width", type=int, default=None,
                    help="绘图宽度上限（步）。给了就取 min(width, %d)" % X_MAX)
    ap.add_argument("--height", type=int, default=None,
                    help="绘图高度上限（步）。给了就取 min(height, %d)" % Y_MAX)
    ap.add_argument("--max-side", type=int, default=700,
                    help="预处理时图片最大边长（默认 700）")
    ap.add_argument("--threshold", type=int, default=128,
                    help="阈值。edge 影响灵敏度，mono 是黑白分界")
    ap.add_argument("--blur", type=int, default=1, help="模糊半径（去噪）")
    ap.add_argument("--simplify", type=float, default=1.0, help="抽稀强度")
    ap.add_argument("--no-thin", action="store_true", help="不做细线化")
    ap.add_argument("--flip-y", action="store_true", default=True,
                    help="Y 轴翻转（默认开）")
    ap.add_argument("--no-flip-y", dest="flip_y", action="store_false",
                    help="关闭 Y 轴翻转")
    ap.add_argument("--ram-kb", type=int, default=22000,
                    help="可用 BASIC 内存 KB，默认 22000")
    ap.add_argument("--preview", metavar="OUT.png",
                    help="另外导出预览图（SVG，可用 magick 转 PNG）")
    args = ap.parse_args(argv)

    plot_w = X_MAX if args.width is None else min(args.width, X_MAX)
    plot_h = Y_MAX if args.height is None else min(args.height, Y_MAX)

    print("读取图片: %s" % args.image)
    w, h, px = read_gray(args.image, args.max_side)
    print("  降采样后 %d x %d 像素" % (w, h))

    print("线条化（mode=%s%s）…" % (args.mode, ", invert" if args.invert else ""))
    mask = to_binary(w, h, px, args.mode, args.threshold, args.blur, args.invert)
    dark = sum(sum(r) for r in mask)
    print("  线条像素 %d (%.1f%%)" % (dark, 100.0 * dark / (w * h)))

    if not args.no_thin:
        print("细线化…")
        mask = thin(dilate(mask, w, h, 1), w, h)
        dark = sum(sum(r) for r in mask)
        print("  细化后 %d 像素" % dark)

    segs = to_segments(mask, w, h, args.simplify)
    print("  折线段 %d 条" % len(segs))
    if not segs:
        sys.exit("没有提取到线条。试试 --threshold 调低，或换成 --mode mono。")

    segs, pw, ph = map_to_plot(segs, w, h, plot_w, plot_h, args.flip_y)
    print("  纸带绘图区 %d x %d 步 (%.1f x %.1f mm)"
          % (pw, ph, pw * MM_PER_UNIT, ph * MM_PER_UNIT))

    stmts = chunk_lines(segs, w)
    print("  有效 LINE 语句 %d 条（丢掉了 %d 条退化线段）"
          % (len(stmts), len(segs) - len(stmts)))
    basic = emit_basic(stmts, pw, ph,
                       title=os.path.splitext(os.path.basename(args.image))[0])

    out = args.output or (os.path.splitext(args.image)[0] + ".bas")
    with open(out, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write(basic)

    nlines = basic.count("\r\n")
    print("写出: %s  (%d 行 BASIC, %d 个 LINE)" % (out, nlines, len(stmts)))

    if args.preview:
        svg_path = os.path.splitext(args.preview)[0] + ".svg"
        export_preview(segs, pw, ph, svg_path)
        print("预览: %s" % svg_path)
        magick = shutil.which("magick") or shutil.which("convert")
        if magick and args.preview.lower().endswith(".png"):
            r = subprocess.run([magick, svg_path, args.preview], capture_output=True)
            if r.returncode == 0:
                print("预览: %s" % args.preview)

    est = nlines * 4 + len(stmts) * 18
    print("内存估算: 约 %d KB（可用 %d KB）" % (est // 1024, args.ram_kb))
    if est > args.ram_kb * 1024 * 0.9:
        print("⚠ 接近内存上限。加大 --ram-kb，或把 --max-side 调小 / --simplify 调大。")
    print()
    print("下一步: ./bas2wav %s" % os.path.basename(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
