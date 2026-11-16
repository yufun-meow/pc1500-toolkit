# PC-1500 Audio ↔ BASIC Environment + MIDI → BEEP Music Generator

An on-device toolkit for the Sharp PC-1500 (TRS-80 PC-2): **convert between BASIC and cassette audio**,
plus a small utility that **turns MIDI files into PC-1500 BEEP music programs**.

No device connection required; every tool runs offline.

---

## Getting Started (Fastest Path)

```bash
cd pc1500
./pc1500ui.py          # GUI with function tabs, just click the buttons
```

See the sections below for command-line usage.

---

## Layout

```
pc1500/
├── pc1500ui.py          ★ GUI (entry point)
├── img2lines.py         image → lines → printer-drawing BASIC
├── midi2beep_pc1500.py  MIDI → PC-1500 BEEP music BASIC
├── bas2wav              BASIC → cassette WAV
├── wav2bas              cassette WAV → BASIC
├── check-wav            check whether a WAV can be used to load
├── demo/                ready-made test files
│   ├── TWINKLE_48k.wav  ★ Twinkle Twinkle, recognisable melody (try this first)
│   ├── TEST_48k.wav     3 notes, verifies BEEP usage
│   ├── SCALE_48k.wav    value2 in even steps, for listening to pitch resolution
│   ├── HELLO_48k.wav    step-by-step test program
│   └── *.bas            corresponding source files
├── bin/                 official Pocket Tools 2.00 (natively built here, code unchanged)
│   ├── bas2img          BASIC source → BASIC intermediate code
│   ├── bin2wav          intermediate code → cassette WAV
│   └── wav2bin          cassette WAV → BASIC source / intermediate code
└── share/
    ├── Pocket_Tools_Manual_200.pdf   official manual
    └── *.c                           original C source of the three tools
```

The three programs in `bin/` come from Torsten Muecker's **Pocket Tools 2.00**
(the originals called internally by
[SharpPocketToolsGUI](https://github.com/SilverGreen93/SharpPocketToolsGUI)).
The source is untouched; it was simply rebuilt for Linux with `gcc -std=gnu89` —
the original is C89 and won't compile with modern gcc's default standard.

`bas2wav` / `wav2bas` are thin wrappers: they pin fixed parameters like `-p 1500`
and leave the encoding rules entirely to the official program. For full manual
control, call the tools in `bin/` directly.

---

## 1. GUI

```bash
./pc1500ui.py
```

Tabs:

| Tab | Purpose |
|---|---|
| MIDI → BEEP Music | pick a MIDI → optionally "preview which tracks exist" → generate `.bas` |
| BASIC → Cassette WAV | pick a `.bas`, enter a save name → generate a WAV, playable directly |
| Cassette WAV → BASIC | pick a recording, choose the source → restore to `.bas` |
| Image → Printer Drawing | pick an image, tweak detail → preview lines → generate a CE-150 drawing program |

The output log is at the bottom and scrolls in real time. Buttons are disabled
during processing.

---

## 2. BASIC ↔ Audio Conversion

### BASIC → Cassette WAV

```bash
./bas2wav program.bas              # -> program.wav
./bas2wav program.bas out.wav
./bas2wav -n MUSIC program.bas     # change save name to MUSIC
./bas2wav -s 3 program.bas         # sync tone length 3 seconds
./bas2wav -r 44k program.bas       # sample rate 44.1 kHz
./bas2wav -k program.bas           # keep intermediate .img for inspection
```

- `-n NAME`: the real machine's `CLOAD "NAME"` looks up the file by this name,
  max 16 characters. Defaults to the output filename.
- `-s SECONDS`: length of the sync tone before the file header, default 2.0.
  A real machine's CSAVE is roughly this long.
- `-r RATE`: `48k` (default) / `16k` / `44k` / `10k`.
  **This is the number-one cause of failed loads**: most USB sound cards only
  support 44100/48000 Hz. Playing a file at any other rate forces resampling,
  which blunts the square-wave edges and the PC-1500 can't lock on.
  `48k` uses zero-order hold to scale exactly to 48000 Hz, so playback involves
  no resampling and is the most reliable.

The output is a mono PCM WAV. **To play it to the PC-1500**:
connect the WAV from the sound card output to the CE-150's EAR input
(or cassette interface), type `CLOAD "MUSIC"` on the machine, then play.
Start with a low volume; too loud or too quiet both cause read errors.

### Cassette WAV → BASIC

```bash
./wav2bas recording.wav            # -> recording.bas
./wav2bas -t img recording.wav     # intermediate code only (byte-for-byte)
./wav2bas -i recording.wav chk.img # both text and intermediate code, for checking
./wav2bas -d CAS recording.wav     # recorded from a cassette deck, not direct
./wav2bas -d AIR recording.wav     # recorded over the air from a beeper
```

**Recording requirements** (official manual):

- PC-1500 sample rate **at least 11025 Hz**, mono, 16-bit preferred
  (8-bit is fine with a strong signal)
- Amplitude close to but **not over the limit / not clipped**
- Press `CSAVE`, wait a second for a steady tone, then start recording
- Don't cut out silent sections in the middle, and don't stop too early at the end
  (recording a bit longer is safer)

---

## ★ Troubleshooting Order When CLOAD Fails on the Machine

First confirm the file itself is fine, then work on the playback chain.

### Step 0: File self-check

```bash
./check-wav yourfile.wav
```

It reports the sample rate, peak, DC offset, and whether the file can be
decoded back to BASIC.

Or just use the ready-made test files:

```bash
cd demo
ls
#  TEST_48k.wav    ★ try this first: only 3 notes, conservative settings, verifies BEEP usage
#  TEST.bas        its source
#  HELLO_48k.wav   ★ full test program (48 kHz, zero resampling)
#  HELLO_44k.wav   use when the sound card is 44100
#  HELLO.bas       source
```

All three WAVs have been verified to decode correctly. On the machine,
`CLOAD "TEST"` or `CLOAD "HELLO"` and then play.
**If none of them load, the problem isn't the file.**

Try `TEST_48k.wav` first — after loading, `RUN` should beep 3 times, low to high.
If this one beeps, the audio chain and the BEEP usage are both correct.

### Step 1: Sample rate (most common cause)

**The problem is the sound card's hardware sample rate.**

Many USB sound cards only support **44100 and 48000 Hz**. Playing a 16 kHz or
10 kHz file forces PipeWire to resample to 48 kHz — and resampling **blunts the
steep edges of the square wave**, so the PC-1500 can't read it.

How to check:

```bash
grep -A12 "Playback:" /proc/asound/card*/stream0 | grep Rates
pactl list short sinks
```

Fix: generate at the same rate as the sound card's native rate, **zero resampling**.

```bash
./bas2wav -r 48k your.bas your.wav      # ★ most reliable, 48 kHz zero-order hold
./bas2wav -r 44k your.bas your.wav      # use when the sound card is 44100
./bas2wav -r 16k your.bas your.wav      # old default
```

What `-r 48k` does: first generate the official bitstream, then use **zero-order
hold** (repeat sample points, no interpolation or filtering) to scale exactly to
48000 Hz / 16-bit. This keeps the square-wave edges steep and PipeWire leaves it
alone entirely.

Verify that playback really isn't resampling:

```bash
pw-play your.wav &
sleep 2
pactl list sink-inputs | grep node.rate     # should show 1/48000
```

### Step 1.5: If the machine shows BREAK IN xx / doesn't beep

**This is a good sign** — it means the audio **loaded successfully**
(it only executes the program if it loaded). The problem is in the generated BASIC itself.

The most common cause: `BEEP`'s first parameter (repeat count) is set to **0**.
0 times = no sound. Every example in the manual is `BEEP 5` / `BEEP 10` / `BEEP 2,M,(Q*D)`.

Check the program you loaded:

```
LIST
```

If you see `BEEP 0,...`, that's the problem. This tool already fixes it;
`midi2beep_pc1500.py` generates `BEEP 1,N,S` (pitch parameter N is at least 1;
rests use an empty loop and emit no BEEP).

Another possibility: `value3` (duration) is too small to hear. The manual examples
use `D=50`, so the 50 range is where sound actually appears; single-digit
durations may be too short to hear.

**First verify with `demo/TEST_48k.wav`** — it has only three notes with
conservative settings:

```basic
10 BEEP 1,60,50
20 WAIT 20
30 BEEP 1,100,50
40 WAIT 20
50 BEEP 1,140,50
60 END
```

After loading, `RUN` should produce 3 beeps, low to high.
- Hear 3 beeps → the BEEP usage is right, the issue is only the music program's parameters
- Still BREAK → the parameters themselves are wrong; send me the error message on screen

### Step 1.6: It beeps but sounds "out of tune / unrecognisable"

This is a BEEP pitch-conversion issue. `midi2beep_pc1500.py` uses the **Swedish formula**
(back-derived from the official manual's music examples):

```
F = K * G / (A + K)      K = 7.455, G = 7918.3
```

Given a pitch parameter A (i.e. BEEP's value2), you can compute the actual
frequency F; conversely, from a MIDI note's frequency you can solve for A,
round it, and clamp it to 0~255.

**BEEP's distinguishable pitch range is narrow.** Notes outside 0~255 are clamped
to the boundary and come out out-of-tune. The tool reports in the log how many
notes were clamped. It's best to keep the melody within roughly
**230 Hz ~ 7 kHz** (the machine's own limit); notes that are too low get folded.

To hear pure resolution, use `demo/SCALE_48k.wav` (value2 from 0 to 240 in steps of +16).
If you hear a roughly evenly rising glide, the mapping is correct.

### Step 2: Wrong output device

```bash
pactl list short sinks          # see available outputs
```

If there are multiple sound cards (USB, HDMI, onboard), **the default one may not
be connected to anything**. Play to the right device:

```bash
PULSE_SINK=<that sink's name> paplay your.wav
```

Or plug headphones directly into the port you intend to use and listen first —
confirm there's sound and that it's a "beep-beep" square wave.

### Step 3: Volume

- First listen in headphones at a **normal** level, then connect to EAR
- The PC-1500 is fairly tolerant of this signal, but **too loud distorts, too
  quiet won't read**
- Try system volume **70%~80%**; if it won't load, try 50% / 90% each once

### Step 4: Wiring

Official manual, verbatim:

> Connect the EAR input of your SHARP cassette interface with the **grey plug**
> preferably to the HEADPHONE output of your computer, or alternatively to the
> LINE OUTput (green) of the sound card.
> **Do not connect the original small black plug (Remote) to the sound card!**

- Use the **grey plug**: CE-150's **EAR** ← the computer's headphone jack
  (preferred) or the sound card's line output (green jack)
- Connect to **EAR**, not MIC
- **Do not connect the small black Remote plug** (leave it floating). The REMOTE
  switch on the CE-150 controls the recorder's remote signal; when feeding audio
  directly, either position is fine
- Push the connector in fully; mono or ordinary stereo cables both work
- Don't try it when the CE-150's power is unstable or the batteries are nearly dead

### Step 5: Timing

The manual requires: **wait 2 seconds after typing CLOAD before playing**.

- First type `CLOAD "HELLO"` on the machine and press Enter
- **Wait 2 seconds**
- Then click play
- The "booo—" at the start is the sync tone; the machine uses it to lock onto the
  frequency, don't skip it

### Step 6: Save name

The name in `CLOAD "HELLO"` must match the name generated by `-n` (max 16 characters).
If unsure, **omit the name** and just `CLOAD` — it will load the first program on the tape.

---

## 3. MIDI → BEEP Music

```bash
./midi2beep_pc1500.py music.mid               # -> music.bas
./midi2beep_pc1500.py music.mid out.bas
./midi2beep_pc1500.py --list-tracks music.mid # just list tracks/note counts
./midi2beep_pc1500.py --track 2 music.mid     # specify a track
```

Flow: mido parses the MIDI → extract notes along the timeline (note_on/note_off
pairing, same-pitch overlap merging, drum channel 9 skipped) → note segmentation
→ map to BEEP parameters → generate BASIC.

The generated program looks like this:

```basic
10 REM PC-1500 BEEP MUSIC FROM MIDI
20 REM music
30 DATA 6
40 DATA 48,120,61,130
50 DATA 0,83,79,140
60 READ X
70 FOR I=1 TO X
80 READ N,S
90 IF N>0 THEN BEEP 1,N,S
100 IF N=0 THEN FOR W=1 TO S:NEXT W
110 NEXT I
120 END
```

A few key points:

- **Data goes on `DATA` lines**, the body is a `READ` + inline `IF` loop with no
  `GOTO` jumps, avoiding jumps into `DATA` lines. More memory-efficient than a
  long string of inline BEEPs.
- **Rests use an empty loop**: an entry with `N=0` is a rest, `S` is the loop count.
  Measured: 1 second ≈ 83 empty loops (`LOOPS_PER_SECOND = 83` in the program);
  rests are not truncated.
- **Duration linear fit**: BEEP's value3 is approximately linear with seconds
  (`S=120→0.40s`, `S=1600→2.90s`); solve for `S` and clamp to 44~1600.
- Line endings are CRLF (the format the PC-1500 requires).

Once you have the `.bas`:

```bash
./bas2wav -n SONG music.bas        # turn it into cassette audio for the machine
```

### Input material suggestions

BEEP can only emit one note at a time, so:

- **Suitable**: single-voice melodies (whistling, flute, monophonic synth, humming, music box)
- **Unsuitable**: chords, piano accompaniment, recordings with heavy reverb/multiple
  voices — they come out out-of-tune

The range is limited to roughly **230 Hz ~ 7 kHz** (the machine's own limit).
Notes that are too low get folded.

---

## 3.5. Image → CE-150 Printer Drawing

Turn any image into a line drawing and generate BASIC that the PC-1500 + CE-150
printer can draw.

```bash
./img2lines.py photo.jpg                     # -> photo.bas
./img2lines.py lineart.png --mode mono       # line-art mode (dark pixels become lines)
./img2lines.py photo.jpg --preview out.png   # also export a preview, see the result first!
./img2lines.py photo.jpg --max-side 600 --simplify 0.5   # finer (longer program)
./img2lines.py photo.jpg --max-side 260 --simplify 2.0   # coarser (less memory)
```

Parameters:

| Parameter | Purpose |
|---|---|
| `--mode edge` | edge detection (default, good for photos) |
| `--mode mono` | dark pixels become lines directly (good for line art, scans, silhouettes) |
| `--paper-mm 57` | paper width in mm, default 57 (CE-150 thermal paper) |
| `--max-side N` | preprocessing detail, default 420. Larger = more lines |
| `--simplify N` | thinning strength, default 1.0. Larger = fewer lines |
| `--threshold N` | sensitivity, default 128. In edge mode, smaller = more lines |
| `--preview out.png` | export a preview image + SVG |

The generated program looks like this:

```basic
10 REM PC-1500 CE-150 DRAWING
30 GRAPH
40 LINE (0,0)-(570,0)
60 LINE (0,0)-(0,428)
90 LINE (496,142)-(357,143):LINE (357,143)-(357,312):...
99 TEXT
```

It uses the CE-150's drawing commands: `GRAPH` enters graphics mode, `GLCURSOR`
positions, `LINE (x1,y1)-(x2,y2)` draws a line, and `TEXT` returns to text mode.

**Memory warning**: the PC-1500 has only 2K of user memory, and a `LINE` takes
about 20 bytes. Too many program lines won't fit — if it overflows, lower
`--max-side` or raise `--simplify`. The tool warns when the line count exceeds 1200.

Same flow as music: `./bas2wav DRAW.bas` generates cassette audio, `CLOAD` then
`RUN` on the machine, and the printer starts drawing.

---

## 4. About the BEEP Conversion (Important, Please Read)

`midi2beep_pc1500.py` generates `BEEP 1,N,S`, where:

| Item | Manual text | Status |
|---|---|---|
| Syntax | `BEEP value1 [,value2] [,value3]` | ✅ manual is explicit |
| value1 | repeat count, 0~65535 | ✅ manual is explicit |
| value2 | frequency, 0~255 | ✅ manual is explicit |
| value3 | duration, 0~65279 | ✅ manual is explicit |
| Range | 256 steps, roughly 230 Hz ~ 7 kHz | ✅ manual p.41 |

**The manual does not give formulas for `value2 → actual Hz` or
`value3 → actual milliseconds`.**

- **Pitch**: the program uses the Swedish formula `F = K*G/(A+K)`
  (K=7.455, G=7918.3), back-derived from the official manual's music examples.
  Given a MIDI note → frequency → solve for A → clamp 0~255.
- **Duration**: the program uses a linear fit, computed from two measurements
  (S=120→0.40s, S=1600→2.90s): `DUR_SLOPE ≈ 0.001689`, `DUR_INTERCEPT ≈ 0.1973`;
  solve for `S` and clamp to 44~1600.
- **Rests**: timed with an empty loop, measured 1 second ≈ 83 loops
  (`LOOPS_PER_SECOND = 83` in the program).

In other words: **pitch comes from a back-derived formula, duration/rests from
measured fits — all still have room for calibration.** To calibrate, edit the
constants at the top of the script:

```python
BEEP_K = 7.455
BEEP_G = 7918.3
DUR_SLOPE = (2.90 - 0.40) / (1600 - 120)
DUR_INTERCEPT = 0.40 - 120 * DUR_SLOPE
LOOPS_PER_SECOND = 83
```

### How to calibrate (do once with the device connected, five minutes)

1. Take a MIDI containing a C major scale, run it through `midi2beep_pc1500.py`,
   then `./bas2wav` to cassette audio.
2. `CLOAD` and `RUN` on the machine; use a tuner app on your phone (or match by
   ear against a piano/guitar) and note the actual pitch.
3. If everything is uniformly high/low → tweak `BEEP_K` / `BEEP_G`;
   if the low range is bunched together and the high range spread out → the
   formula shape needs changing (could switch to linear or a lookup table).
4. Time a note's duration with a stopwatch and back-compute `DUR_SLOPE` /
   `DUR_INTERCEPT`; time a rest and back-compute `LOOPS_PER_SECOND`.

After editing, just re-run the script; no code changes needed.

---

## 5. Verified / Unverified

**Verified** (offline):
- BASIC → intermediate code → WAV → BASIC round-trip, content character-for-character identical
- `-t img` round-trip, intermediate code byte-for-byte identical
- Filename written correctly (the one the real machine's `CLOAD "NAME"` uses)
- MIDI parsing: `--list-tracks` correctly lists tracks and note counts;
  drum channel 9 is skipped; same-pitch overlaps are merged; notes shorter than
  30 ms are filtered out
- Generated BASIC is accepted by the official compiler

**Unverified / known issues**:
- **Real-machine audio loading has succeeded**: the machine reporting `BREAK IN 50`
  means the WAV was correctly loaded and executed; the audio-encoding path works.
- **value1 must not be 0** (0 times = silence; measured no sound / BREAK). The
  manual examples are all 1/2/5/10; now `BEEP 1,N,S` is generated uniformly.
- value3's exact unit is still undetermined. The script uses a linear fit (44~1600);
  the manual example `D=50` produces sound, so durations should be in the
  tens-to-hundreds range.
- The rest empty-loop coefficient `LOOPS_PER_SECOND = 83` is a measured value
  (5000 loops ≈ 14.2 seconds); it may need re-measuring on a different machine /
  BASIC interpreter.
- The pitch formula is back-derived from official examples, **not calibrated
  note-by-note on the real machine**; out-of-range notes are clamped.
- A third-party sample I have, `lecon-de-musique.wav`, doesn't decode to correct
  content (file header and checksum are correct, but the body is misaligned).
  Cause undetermined; it may be a synthetic file rather than a real-machine CSAVE.
  **Trust recordings from a real machine.**

---

## References

- Official Pocket Tools manual: `share/Pocket_Tools_Manual_200.pdf`
- Original tool source: `share/*.c`
- PC-1500 official user manual (BEEP on p.165-167, range notes on p.41)
