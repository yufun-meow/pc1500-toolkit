#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
midi2beep_pc1500.py —— MIDI -> PC-1500 BEEP 音乐 BASIC（线性时长 + 休止处理）

改动：
  1. 休止条目用实测空循环系数：5000 次 ≈ 14.2 秒 → 1 秒 ≈ 352 次循环。
  2. 生成的 BASIC 不再用 GOTO 跳转，改用内联 IF：
       IF N>0 THEN BEEP 1,N,S
       IF N=0 THEN FOR W=1 TO S:NEXT W
     避免 GOTO 跳到 DATA 行。
  3. 休止不截断，S 原样写入 DATA。

音高映射、时长线性拟合保持不变。
"""

import argparse
import os
import sys

try:
    import mido
except ImportError:
    sys.exit("需要 mido：pip install mido")

# BEEP 音高参数合法范围
PARAM_MIN = 0
PARAM_MAX = 255

# 瑞典公式常量：F = K * G / (A + K)
BEEP_K = 7.455
BEEP_G = 7918.3

# 时长线性拟合参数（由 S=120→0.40s, S=1600→2.90s 算出）
DUR_SLOPE = (2.90 - 0.40) / (1600 - 120)      # ≈ 0.001689
DUR_INTERCEPT = 0.40 - 120 * DUR_SLOPE        # ≈ 0.1973

# 下限与上限
MIN_BEEP_DUR = 44
MAX_BEEP_DUR = 1600

# 休止判定阈值（秒）
REST_GAP_THRESHOLD = 0.05

# 实测空循环系数：5000 次 ≈ 14.2 秒 → 1 秒 ≈ 352 次
LOOPS_PER_SECOND = 83

DRUM_CHANNEL = 9


def note_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def param_to_freq(param):
    return BEEP_K * BEEP_G / (param + BEEP_K)


def freq_to_param(freq):
    if freq <= 0:
        return PARAM_MAX
    a = BEEP_K * BEEP_G / freq - BEEP_K
    a = int(round(a))
    return max(PARAM_MIN, min(PARAM_MAX, a))


def note_to_param_exact(note):
    return freq_to_param(note_to_freq(note))


def seconds_to_dur_param(seconds):
    """目标时长(秒) -> BEEP 时长参数 S。基于线性拟合反解。"""
    s = (seconds - DUR_INTERCEPT) / DUR_SLOPE
    s = int(round(s))
    return max(MIN_BEEP_DUR, min(MAX_BEEP_DUR, s))


def seconds_to_loops(seconds):
    """目标时长(秒) -> 空循环次数。用于休止。不截断。"""
    loops = int(round(seconds * LOOPS_PER_SECOND))
    if loops < 1:
        loops = 1
    return loops


def duration_to_param(seconds, param):
    return seconds_to_dur_param(seconds)


def list_tracks(path):
    mid = mido.MidiFile(path, clip=True)
    print("文件: %s" % path)
    print("类型: %d, 轨道数: %d, 每拍 tick: %d, 长度: %.1f 秒"
          % (mid.type, len(mid.tracks), mid.ticks_per_beat, mid.length))
    for i, tr in enumerate(mid.tracks):
        notes = 0
        chans = set()
        for m in tr:
            if m.type == "note_on" and m.velocity > 0:
                notes += 1
                chans.add(getattr(m, "channel", 0))
        chan_str = ",".join(str(c) for c in sorted(chans)) if chans else "-"
        print("  轨道 %d: %-40s 音符 %d  通道 %s"
              % (i, tr.name or "(无名)", notes, chan_str))


def pick_best_track(mid):
    best_idx, best_score = 0, -1
    for i, tr in enumerate(mid.tracks):
        notes = []
        for m in tr:
            if m.type == "note_on" and m.velocity > 0:
                if getattr(m, "channel", 0) == DRUM_CHANNEL:
                    continue
                notes.append(m.note)
        if not notes:
            continue
        avg_pitch = sum(notes) / float(len(notes))
        score = len(notes) * (1.0 + avg_pitch / 128.0)
        if score > best_score:
            best_score, best_idx = score, i
    return best_idx


def extract_notes(track, ticks_per_beat, default_tempo=500000):
    events = []
    t = 0.0
    tempo = default_tempo

    for msg in track:
        if msg.type == "set_tempo":
            tempo = msg.tempo
        t += mido.tick2second(msg.time, ticks_per_beat, tempo)

        if msg.type == "note_on" and msg.velocity > 0:
            if getattr(msg, "channel", 0) == DRUM_CHANNEL:
                continue
            events.append((t, msg.note, "on"))
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if getattr(msg, "channel", 0) == DRUM_CHANNEL:
                continue
            events.append((t, msg.note, "off"))

    open_notes = {}
    notes = []
    last_t = 0.0
    for (when, note, kind) in events:
        last_t = max(last_t, when)
        if kind == "on":
            if note in open_notes and open_notes[note]:
                start = open_notes[note].pop(0)
                dur = when - start
                if dur > 0.01:
                    notes.append((start, dur, note))
            open_notes.setdefault(note, []).append(when)
        else:
            starts = open_notes.get(note)
            if starts:
                start = starts.pop(0)
                dur = when - start
                if dur > 0.01:
                    notes.append((start, dur, note))

    for note, starts in open_notes.items():
        for start in starts:
            dur = max(0.05, last_t - start)
            notes.append((start, dur, note))

    notes.sort(key=lambda x: (x[0], -x[2]))
    filtered = []
    for (start, dur, note) in notes:
        if dur < 0.03:
            continue
        if filtered and abs(start - filtered[-1][0]) < 0.03:
            if note > filtered[-1][2]:
                filtered[-1] = (start, dur, note)
            continue
        filtered.append((start, dur, note))

    filtered.sort(key=lambda x: x[0])
    merged = []
    for (start, dur, note) in filtered:
        if merged and merged[-1][2] == note and start - (merged[-1][0] + merged[-1][1]) < 0.05:
            s0, d0, n0 = merged[-1]
            merged[-1] = (s0, start + dur - s0, n0)
        else:
            merged.append((start, dur, note))

    print("extract_notes: last_t = %.2f 秒, 音符数 = %d" % (last_t, len(merged)))
    for n in merged[:10]:
        print("  onset=%.3f dur=%.3f note=%d" % n)

    return merged


def emit_basic(notes, title="", step=10):
    out = []
    n = step

    def add(text):
        nonlocal n
        out.append((n, text))
        n += step

    safe = title[:36]
    add("REM PC-1500 BEEP MUSIC FROM MIDI")
    if safe:
        add("REM %s" % safe)

    entries = []
    clipped = 0
    for i, (start, dur, note) in enumerate(notes):
        param = note_to_param_exact(note)
        f = note_to_freq(note)
        raw_a = BEEP_K * BEEP_G / f - BEEP_K
        if raw_a < PARAM_MIN or raw_a > PARAM_MAX:
            clipped += 1
        dur_param = duration_to_param(dur, param)
        entries.append((param, dur_param))

        if i + 1 < len(notes):
            next_start = notes[i + 1][0]
            gap = next_start - (start + dur)
            if gap > REST_GAP_THRESHOLD:
                rest_loops = seconds_to_loops(gap)
                entries.append((0, rest_loops))   # N=0 表示休止，S 为循环次数

    if clipped:
        print("注意：%d 个音符音高超出 BEEP 参数范围，已截断到边界。" % clipped)

    add("DATA %d" % len(entries))

    buf = []
    for (p, c) in entries:
        buf.append("%d,%d" % (p, c))
        if len(buf) == 4:
            add("DATA " + ", ".join(buf))
            buf = []
    if buf:
        add("DATA " + ", ".join(buf))

    add("READ X")
    add("FOR I=1 TO X")
    add("READ N,S")
    add("IF N>0 THEN BEEP 1,N,S")
    add("IF N=0 THEN FOR W=1 TO S:NEXT W")
    add("NEXT I")
    add("END")

    return "".join("%d %s\r\n" % (ln, tx) for ln, tx in out)


def main(argv):
    ap = argparse.ArgumentParser(description="MIDI -> PC-1500 BEEP 音乐 BASIC（含休止）")
    ap.add_argument("midi", help="输入 MIDI 文件")
    ap.add_argument("output", nargs="?", help="输出 .bas")
    ap.add_argument("--track", type=int, default=None)
    ap.add_argument("--list-tracks", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.exists(args.midi):
        sys.exit("找不到 MIDI: %s" % args.midi)

    if args.list_tracks:
        list_tracks(args.midi)
        return 0

    mid = mido.MidiFile(args.midi, clip=True)

    idx = args.track if args.track is not None else pick_best_track(mid)
    if idx < 0 or idx >= len(mid.tracks):
        sys.exit("轨道号越界: %d" % idx)
    track = mid.tracks[idx]
    print("使用轨道 %d: %s" % (idx, track.name or "(无名)"))

    notes = extract_notes(track, mid.ticks_per_beat)
    print("MIDI 总长: %.2f 秒" % mid.length)

    if not notes:
        sys.exit("这条轨道没有音符。用 --list-tracks 看看别的轨。")
    print("提取音符 %d 个" % len(notes))

    pitches = [x[2] for x in notes]
    print("音高范围: %d .. %d (跨度 %d 半音)"
          % (min(pitches), max(pitches), max(pitches) - min(pitches)))

    title = os.path.splitext(os.path.basename(args.midi))[0]
    basic = emit_basic(notes, title=title)

    out = args.output or (os.path.splitext(args.midi)[0] + ".bas")
    with open(out, "w", encoding="ascii", errors="replace", newline="") as f:
        f.write(basic)
    print("写出: %s (%d 行)" % (out, basic.count("\r\n")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
