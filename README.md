# PC-1500 音频 ↔ BASIC 环境 + MIDI → BEEP 音乐生成器

给 Sharp PC-1500（TRS-80 PC-2）用的本机工具集：**BASIC 与磁带音频互转**，
外加一个**把 MIDI 文件转成 PC-1500 BEEP 音乐程序**的小工具。

不需要连接设备即可使用；所有工具都能离线跑通。

---

## 怎么开始（最快路径）

```bash
cd pc1500
./pc1500ui.py          # 图形界面，功能页点按钮就行
```

命令行的用法见下面各节。

---

## 目录

```
pc1500/
├── pc1500ui.py          ★ 图形界面（入口）
├── img2lines.py         图片 → 线条 → 打印机绘图 BASIC
├── midi2beep_pc1500.py  MIDI → PC-1500 BEEP 音乐 BASIC
├── bas2wav              BASIC → 磁带 WAV
├── wav2bas              磁带 WAV → BASIC
├── check-wav            检查一个 WAV 能不能用来装载
├── demo/                现成的测试文件
│   ├── TWINKLE_48k.wav  ★ 小星星，能听出旋律（推荐先试）
│   ├── TEST_48k.wav     3 个音，验证 BEEP 用法
│   ├── SCALE_48k.wav    value2 均匀步进，用来听音高分辨率
│   ├── HELLO_48k.wav    分步测试程序
│   └── *.bas            各自的源码
├── bin/                 官方 Pocket Tools 2.00（本机原生编译，未改代码）
│   ├── bas2img          BASIC 源码 → BASIC 中间码
│   ├── bin2wav          中间码 → 磁带 WAV
│   └── wav2bin          磁带 WAV → BASIC 源码 / 中间码
└── share/
    ├── Pocket_Tools_Manual_200.pdf   官方手册
    └── *.c                           三个工具的原始 C 源码
```

`bin/` 里的三个程序来自 Torsten Muecker 的 **Pocket Tools 2.00**
（[SharpPocketToolsGUI](https://github.com/SilverGreen93/SharpPocketToolsGUI) 内部调用的原版）。
源码没改，只是用 `gcc -std=gnu89` 重新编译成 Linux 版——
原代码是 C89 的，新版 gcc 默认标准编译不过。

`bas2wav` / `wav2bas` 只是薄包装：把 `-p 1500` 之类固定参数收好，
编码规则完全交给官方程序。想完全手动控制就直接调 `bin/` 里的。

---

## 一、图形界面

```bash
./pc1500ui.py
```

功能页：

| 标签页 | 作用 |
|---|---|
| MIDI → BEEP 音乐 | 选 MIDI → 可先「看看有哪些轨道」→ 生成 `.bas` |
| BASIC → 磁带 WAV | 选 `.bas`，填保存名 → 生成 WAV，可直接播放 |
| 磁带 WAV → BASIC | 选录音，选录音来源 → 还原成 `.bas` |
| 图片 → 打印机绘图 | 选图片、调细节 → 预览线条 → 生成 CE-150 绘图程序 |

输出日志在下方，实时滚动。处理期间按钮会自动禁用。

---

## 二、BASIC ↔ 音频互转

### BASIC → 磁带 WAV

```bash
./bas2wav 程序.bas                 # -> 程序.wav
./bas2wav 程序.bas out.wav
./bas2wav -n MUSIC 程序.bas        # 保存名改成 MUSIC
./bas2wav -s 3 程序.bas            # 同步时长 3 秒
./bas2wav -r 44k 程序.bas          # 采样率 44.1 kHz
./bas2wav -k 程序.bas              # 保留中间 .img 便于核对
```

- `-n 名字`：真机用 `CLOAD "名字"` 按这个名字找文件，最多 16 字符。
  默认取输出文件名。
- `-s 秒`：文件头前的同步单音长度，默认 2.0。真机 CSAVE 大约就是这个长度。
- `-r 采样率`：`48k`（默认）/ `16k` / `44k` / `10k`。
  **这个是读不出的头号原因**：多数 USB 声卡只有 44100/48000 Hz，
  播其它采样率的文件会被重采样，方波边沿被削弱，PC-1500 就锁不住。
  `48k` 用零阶保持精确放大到 48000 Hz，播放时零重采样，最稳。

生成的是单声道 PCM WAV。**播给 PC-1500 听**：
把 WAV 从声卡输出接到 CE-150 的 EAR 输入（或磁带接口），
机器上敲 `CLOAD "MUSIC"` 后播放。音量从较小开始试，太大太小都会读错。

### 磁带 WAV → BASIC

```bash
./wav2bas 录音.wav                 # -> 录音.bas
./wav2bas -t img 录音.wav          # 只要中间码（逐字节原样）
./wav2bas -i 录音.wav chk.img      # 文本 + 中间码都出，便于核对
./wav2bas -d CAS 录音.wav          # 录自磁带机而非直连
./wav2bas -d AIR 录音.wav          # 对着蜂鸣器外录
```

**录音要求**（官方手册）：

- PC-1500 采样率**至少 11025 Hz**，单声道，16-bit 更好（信号强时 8-bit 也行）
- 幅度接近但**别超过上限/别限幅**
- 先按 `CSAVE`，等一秒出现稳定声音之后再开始录
- 中间静音段不要剪掉，结尾也别急着停（多录一会儿更保险）

---

## ★ 机器上 CLOAD 读不出来时的排查顺序

先确认文件本身没问题，再动播放链路。

### 第 0 步：文件自检

```bash
./check-wav 你的文件.wav
```

它会告诉你采样率、峰值、直流偏移，以及能不能被解码回 BASIC。

或者直接用现成的测试文件：

```bash
cd demo
ls
#  TEST_48k.wav    ★ 先试这个：只有 3 个音，参数保守，用来验证 BEEP 用法
#  TEST.bas        它对应的源码
#  HELLO_48k.wav   ★ 完整的测试程序（48 kHz，零重采样）
#  HELLO_44k.wav   声卡是 44100 时用
#  HELLO.bas       源码
```

三个 WAV 都验证过能正确解码。机器上 `CLOAD "TEST"` 或 `CLOAD "HELLO"` 然后播放。
**如果都读不出，就不是文件的问题。**

先试 `TEST_48k.wav`——它载入后 `RUN` 应该响 3 声由低到高的"嘀"。
如果这个能响，说明音频链路和 BEEP 用法都是对的。

### 第 1 步：采样率（最常见原因）

**问题在于声卡的硬件采样率。**

很多 USB 声卡只支持 **44100 和 48000 Hz** 两种。如果播放 16 kHz 或
10 kHz 的文件，PipeWire 必须先重采样到 48 kHz —— 而重采样会**削弱方波的陡峭边沿**，
PC-1500 读不出来。

判断方法：

```bash
grep -A12 "Playback:" /proc/asound/card*/stream0 | grep Rates
pactl list short sinks
```

解决办法：生成和声卡原生一致的采样率，**零重采样**。

```bash
./bas2wav -r 48k 你的.bas 你的.wav      # ★ 最稳，48 kHz 零阶保持
./bas2wav -r 44k 你的.bas 你的.wav      # 声卡是 44100 时用
./bas2wav -r 16k 你的.bas 你的.wav      # 旧默认
```

`-r 48k` 的做法：先生成官方位流，再用**零阶保持**（重复采样点，不插值不过滤）
精确放大到 48000 Hz / 16-bit。这样方波边沿保持陡峭，PipeWire 完全不动它。

验证播放时确实没重采样：

```bash
pw-play 你的.wav &
sleep 2
pactl list sink-inputs | grep node.rate     # 应该看到 1/48000
```

### 第 1.5 步：如果机器显示 BREAK IN xx / 不发声

**这是个好迹象**——说明音频**已经载入成功**了（能载入才会去执行程序）。
问题出在生成的 BASIC 本身。

最常见的原因：`BEEP` 的第一个参数（发几次）写成了 **0**。
0 次 = 不发声。手册里所有例子都是 `BEEP 5` / `BEEP 10` / `BEEP 2,M,(Q*D)`。

检查你载入的程序：

```
LIST
```

看到 `BEEP 0,...` 就是这个问题。本工具已修正，`midi2beep_pc1500.py` 生成的是
`BEEP 1,N,S`（音高参数 N 至少为 1；休止用空循环，不发 BEEP）。

另一个可能：`value3`（时长）太小听不见。手册示例用 `D=50`，
所以 50 这个量级才有声音，个位数的时长可能短到听不出来。

**先用 `demo/TEST_48k.wav` 验证**——它只有三个音，参数保守：

```basic
10 BEEP 1,60,50
20 WAIT 20
30 BEEP 1,100,50
40 WAIT 20
50 BEEP 1,140,50
60 END
```

载入后 `RUN`，应该听到 3 声由低到高的"嘀"。
- 听到 3 声 → 说明 BEEP 用法对了，问题只在音乐程序的参数
- 还是 BREAK → 参数本身有问题，把屏幕上的错误信息发给我

### 第 1.6 步：能响但"跑调/听不出是什么歌"

这是 BEEP 音高换算的问题。`midi2beep_pc1500.py` 采用**瑞典公式**
（反推自官方手册音乐示例）：

```
F = K * G / (A + K)      K = 7.455，G = 7918.3
```

给定音高参数 A（即 BEEP 的 value2），就能算出实际频率 F；反过来由 MIDI 音符
算出的频率也能解出 A，四舍五入后截断到 0~255。

**BEEP 的可分辨音区很窄。** 超出 0~255 的音会被截断到边界，转出来会走调。
工具会在日志里报告有多少个音符被截断。建议把旋律限制在大约
**230 Hz ~ 7 kHz**（机器本身的上限）内，太低的音会被折叠。

如果想听纯分辨率，用 `demo/SCALE_48k.wav`（value2 从 0 到 240 每步 +16）。
如果听到的是一条大致均匀上升的滑音，说明映射正确。

### 第 2 步：输出设备选错

```bash
pactl list short sinks          # 看有哪些输出
```

如果有多个声卡（USB 声卡、HDMI、主板声卡），**默认的那个可能根本没接线**。
指定正确的设备播放：

```bash
PULSE_SINK=<那个sink的名字> paplay 你的.wav
```

或者先用耳机直接插在你要用的口上听一遍，确认有声音、并且是"滴滴"的方波声。

### 第 3 步：音量

- 先在耳机里听音量**正常**，再接 EAR
- PC-1500 对这种信号要求挺宽容，但**过大会失真、过小读不到**
- 建议用系统音量 **70%~80%** 试，读不出就 50% / 90% 各试一次

### 第 4 步：接线

官方手册原文：

> Connect the EAR input of your SHARP cassette interface with the **grey plug**
> preferably to the HEADPHONE output of your computer, or alternatively to the
> LINE OUTput (green) of the sound card.
> **Do not connect the original small black plug (Remote) to the sound card!**

- 用**灰色插头**：CE-150 的 **EAR** ← 电脑耳机口（首选）或声卡线路输出（绿口）
- 接的是 **EAR**，不是 MIC
- **黑色 Remote 小插头不要接**（保持悬空）。CE-150 上那个 REMOTE 开关是管
  录音机遥控信号的，直接馈入音频时拨哪边都行
- 接头要插到位；单声道或普通立体声线都可以
- 别在 CE-150 供电不稳、电池快没电时试

### 第 5 步：时序

手册要求：**敲完 CLOAD 后等 2 秒再播放**。

- 先在机器上敲 `CLOAD "HELLO"` 按回车
- **等 2 秒**
- 然后再点播放
- 开头那段"嘟——"是同步音，机器靠它锁定频率，别跳过

### 第 6 步：保存名

`CLOAD "HELLO"` 里的名字必须和 `-n` 参数生成的名字一致（最多 16 字符）。
不确定就**不写名字**直接 `CLOAD`，它会载入磁带上第一个程序。

---

## 三、MIDI → BEEP 音乐

```bash
./midi2beep_pc1500.py 音乐.mid               # -> 音乐.bas
./midi2beep_pc1500.py 音乐.mid out.bas
./midi2beep_pc1500.py --list-tracks 音乐.mid # 只看有哪些轨道/音符数
./midi2beep_pc1500.py --track 2 音乐.mid     # 指定轨道
```

流程：mido 解析 MIDI → 按时间线提取音符（含 note_on/note_off 配对、
同音重叠合并、鼓通道 9 跳过）→ 音符切分 → 映射成 BEEP 参数 → 生成 BASIC。

生成的程序长这样：

```basic
10 REM PC-1500 BEEP MUSIC FROM MIDI
20 REM 音乐
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

几个要点：

- **数据放 `DATA` 行**，主体是 `READ` + 内联 `IF` 循环，不用 `GOTO` 跳转，
  避免跳到 `DATA` 行。比一长串内联 BEEP 省内存。
- **休止用空循环**：条目 `N=0` 表示休止，`S` 是循环次数。
  实测 1 秒 ≈ 83 次空循环（程序里 `LOOPS_PER_SECOND = 83`），休止不截断。
- **时长线性拟合**：BEEP 的 value3 与秒数近似线性
  （`S=120→0.40s`，`S=1600→2.90s`），反解出 `S` 并截断到 44~1600。
- 行尾是 CRLF（PC-1500 需要的格式）。

拿到 `.bas` 之后：

```bash
./bas2wav -n SONG 音乐.bas         # 再变成磁带音频给机器播
```

### 输入素材建议

BEEP 一次只能发一个音，所以：

- **适合**：单声部旋律（口哨、长笛、单音电子琴、哼唱、八音盒）
- **不适合**：和弦、钢琴伴奏、带强烈混响/多音的录音——转出来会走调

音域限制在大约 **230 Hz ~ 7 kHz**（机器本身的上限）。太低的音会被折叠。

---

## 三点五、图片 → CE-150 打印机绘图

把任意图片变成线条画，生成 PC-1500 + CE-150 打印机能画出来的 BASIC。

```bash
./img2lines.py 照片.jpg                     # -> 照片.bas
./img2lines.py 线稿.png --mode mono          # 线稿模式（深色像素当线）
./img2lines.py 照片.jpg --preview out.png    # 顺便导出预览图，先看效果！
./img2lines.py 照片.jpg --max-side 600 --simplify 0.5   # 更细（程序更长）
./img2lines.py 照片.jpg --max-side 260 --simplify 2.0   # 更粗（省内存）
```

参数：

| 参数 | 作用 |
|---|---|
| `--mode edge` | 边缘检测（默认，适合照片） |
| `--mode mono` | 深色像素直接当线（适合线稿、扫描件、剪影） |
| `--paper-mm 57` | 纸宽毫米，默认 57（CE-150 热敏纸） |
| `--max-side N` | 预处理细节，默认 420。越大线越多 |
| `--simplify N` | 抽稀强度，默认 1.0。越大线越少 |
| `--threshold N` | 灵敏度，默认 128。edge 模式越小线越多 |
| `--preview out.png` | 导出预览图 + SVG |

生成的程序长这样：

```basic
10 REM PC-1500 CE-150 DRAWING
30 GRAPH
40 LINE (0,0)-(570,0)
60 LINE (0,0)-(0,428)
90 LINE (496,142)-(357,143):LINE (357,143)-(357,312):...
99 TEXT
```

用的是 CE-150 的绘图指令：`GRAPH` 进入绘图模式，`GLCURSOR` 定位，
`LINE (x1,y1)-(x2,y2)` 画线，最后 `TEXT` 回到文字模式。

**内存提醒**：PC-1500 只有 2K 用户内存，一个 LINE 大约占 20 字节。
程序行数太多会放不下——超了就把 `--max-side` 调小或 `--simplify` 调大。
工具会在行数超过 1200 时提示。

流程同音乐：`./bas2wav DRAW.bas` 生成磁带音频，机器上 `CLOAD` 后 `RUN`，
打印机就开始画。

---

## 四、关于 BEEP 的换算（重要，请读）

`midi2beep_pc1500.py` 生成 `BEEP 1,N,S`，其中：

| 项 | 手册原文 | 状态 |
|---|---|---|
| 语法 | `BEEP value1 [,value2] [,value3]` | ✅ 手册明确 |
| value1 | 重复次数，0~65535 | ✅ 手册明确 |
| value2 | 频率，0~255 | ✅ 手册明确 |
| value3 | 时长，0~65279 | ✅ 手册明确 |
| 音域 | 256 档，约 230 Hz ~ 7 kHz | ✅ 手册 p.41 |

**手册没有给出 `value2 → 具体 Hz` 和 `value3 → 具体毫秒` 的公式。**

- **音高**：程序里用瑞典公式 `F = K*G/(A+K)`（K=7.455，G=7918.3），
  给定 MIDI 音符 → 频率 → 反解 A → 截断 0~255。
- **时长**：程序里用线性拟合，由两处实测（S=120→0.40s、S=1600→2.90s）算出
  `DUR_SLOPE ≈ 0.001689`、`DUR_INTERCEPT ≈ 0.1973`，反解 `S` 并截断到 44~1600。
- **休止**：用空循环计时，实测 1 秒 ≈ 83 次循环（程序里 `LOOPS_PER_SECOND = 83`）。

也就是说：**音高来自公式反推，时长/休止来自实测拟合，都还有校准空间。**
想校准就改脚本顶部的常量：

```python
BEEP_K = 7.455
BEEP_G = 7918.3
DUR_SLOPE = (2.90 - 0.40) / (1600 - 120)
DUR_INTERCEPT = 0.40 - 120 * DUR_SLOPE
LOOPS_PER_SECOND = 83
```

### 怎么校准（连上设备后做一次，五分钟）

1. 拿一份包含 C 大调音阶的 MIDI，跑一遍 `midi2beep_pc1500.py`，
   再 `./bas2wav` 成磁带音频。
2. 机器上 `CLOAD` 后 `RUN`，拿手机装个调音器 App（或用耳朵对钢琴/吉他），
   记下实际音高。
3. 如果整体偏高/偏低 → 微调 `BEEP_K` / `BEEP_G`；
   如果低音区挤在一起、高音区拉开 → 说明公式形态要换（可改为线性或查表）。
4. 用秒表量一个音的时长，反算 `DUR_SLOPE` / `DUR_INTERCEPT`；
   量一段休止，反算 `LOOPS_PER_SECOND`。

改完直接重新跑脚本，不用改代码。

---



## 参考资料

- 官方 Pocket Tools 手册：`share/Pocket_Tools_Manual_200.pdf`
- 工具原始源码：`share/*.c`
- PC-1500 官方使用手册（BEEP 在 p.165-167，音域说明在 p.41）
