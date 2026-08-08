# 🎬 Video Clipper — AI 视频切片 / 直播切片工具包

> 把一段直播回放或长视频，自动变成「带时间表的高光标注 + 带说话人字幕」→ 切成多条短视频 → 自动出成片。
> 面向自媒体创作者、直播切片号、二创与内容运营。**多 Agent 通用，主流程纯本地，模型可换。**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![ffmpeg](https://img.shields.io/badge/ffmpeg-required-orange)](https://ffmpeg.org)

## ✨ 特性

| 能力 | 说明 |
|---|---|
| 🎙️ 语音识别 | faster-whisper 词级 ASR，时间戳精确到词 |
| 👥 音色识别 / 说话人分离 | pyannote 多主播 PK / 多人连麦，字幕带 `[S0]/[S1]` 标签 |
| 🎯 高播放量分析 | LLM 四维评分（信息价值/情感共鸣/传播潜力/结构完整），标注爆点类型 + 具体时间 + 推荐理由 + 标题 |
| 📋 自主切片模式 | 一键产出完整时间表 `timeline.md` + 高光 `edl.json` |
| 📝 带时间表的字幕 | `subtitles.srt`（含说话人标签），可直接导入剪映 |
| ✂️ 自动切割 | ffmpeg 词边界切割 + 30ms 淡入淡出，杜绝爆音 |
| 🎬 自动成片 | 9:16 / 16:9 / 1:1 画幅 + 字幕烧录 + 多片段拼接 |
| 🧩 13 种切片类型 | 电商/娱乐/游戏/知识/观点/演讲/故事/才艺/直播互动(PK连麦)/体验/评测/情感/资讯，每种独立处理策略 |
| 🤖 多 Agent / 多模型 | 纯 Markdown 流程 + 纯 Python CLI，Claude Code / Codex / OpenCode / Hermes 及任意 agent 可用；分析层走 OpenAI 兼容 API（DeepSeek/豆包/Kimi/GPT/Claude/通义/MiniMax…） |

## 🏗️ 架构

```
输入视频/直播回放
   │
   ▼ ① transcribe.py   ffmpeg 抽音频 → faster-whisper 词级 ASR → transcripts/*.json（缓存）
   │
   ▼ ② diarize.py      （多人场景）pyannote 音色分离 → 句子打 S0/S1/S2… 标签（无 torch 自动降级）
   │
   ▼ ③ audio_signal.py  （可选）兴奋点检测：笑声/掌声/尖叫/高能段落（辅助 LLM）
   │
   ▼ ④ analyze.py       LLM 按切片类型读时间表 → highlights.json / edl.json
   │                      （高光时间点 + 爆点类型 + 评分 0-1 + 理由 + 标题）
   │
   ▼ ⑤ 产出            timeline.md（时间表） + subtitles.srt（带说话人）→ 人工确认
   │
   ▼ ⑥ cut.py           按 EDL 词边界切割 → clips/*.mp4（30ms 淡入淡出）
   │
   ▼ ⑦ render.py        画幅转换 + 字幕烧录 + 拼接 → final/*.mp4 成片
```

## 🚀 快速开始

### 环境

```bash
# ffmpeg + Python 3.10+
pip install faster-whisper numpy
# 音色分离（可选）：pip install torch torchaudio pyannote.audio + HuggingFace token
```

### 一条龙（自主切片模式）

```bash
# ① 转写（中文推荐 large-v3；CPU 可 small/medium + int8）
python scripts/transcribe.py input.mp4 --model large-v3 --language zh

# ② 时间表 + 带说话人字幕
python scripts/build_timeline.py clip_work/transcripts/*.json --with-speakers

# ③ LLM 高光分析（类型见下；配置 LLM_API_BASE / LLM_API_KEY / LLM_MODEL）
python scripts/analyze.py clip_work/timeline/xxx_timeline.md --type ecommerce

# ④ 切割成片
python scripts/cut.py clip_work/highlights/xxx_edl.json
python scripts/render.py clip_work/clips --format 9:16 --subtitles clip_work/timeline/xxx.srt
```

### 切片类型

`ecommerce` 电商带货 · `entertainment` 娱乐综艺 · `game` 游戏高光 · `knowledge` 知识干货 · `opinion` 观点输出 · `speech` 演讲口播 · `story` 故事剧情 · `talent` 才艺表演 · `live_interaction` 直播互动(连麦/PK) · `experience` 产品体验 · `review` 内容评测 · `emotion` 情感陪伴 · `news` 新闻资讯

### 三种运行模式

- **交互模式（默认）**：agent 先提问切片类型/时长/平台/人数/输出物，再执行
- **自主模式**：`全自动` 直接跑完七步
- **半自动**：只出时间表和字幕，人工挑选后再切

## ⚠️ 注意事项（硬规则，违反会出问题）

1. **词边界切割**：切点必须落在 whisper 词时间戳边界上，绝不切断音节/字（`cut.py` 自动保证；手写 EDL 时同样遵守）。
2. **30ms 音频淡入淡出**：每个切点 `afade` 0.03s，否则拼接处有爆音。
3. **字幕最后加**：先叠完所有效果（动效/转场）再烧字幕，否则字幕被遮挡。
4. **转写缓存**：源文件不变就永不重转写（`transcripts/` 下有缓存）；换模型参数才重跑。
5. **高光时间点必须落在句子/语义边界**：以转写文本为准，绝不硬切（`analyze.py` 自动吸附到句子边界）。
6. **字幕文本用转写原文**：不做「美化改写」；如要修正错别字，逐字对比后再改。
7. **时长紧凑**：切片宁短勿长，前 3 秒必须有钩子（福利/金句/冲突/悬念），平台完播率法则。
8. **ASR 必须词级模式**：禁用 SRT/句子级输出做分析——丢失亚秒级边界，切割会不准。
9. **不在源目录写东西**：一切产物进 `clip_work/`，源文件永不被修改。
10. **先出时间表再动手切**：即使自主模式，也先给用户过目 `timeline.md`（除非明确要求直接出片）。

**模型选择建议**：中文正式发布用 `large-v3`（small/medium 会有错字）；CPU 跑加 `--compute int8`；长视频可用 `--start/--end` 分段处理。

## 🧩 依赖与配套插件

### 核心依赖（必须）

| 依赖 | 用途 |
|---|---|
| **ffmpeg + ffprobe** | 音频提取 / 切割 / 渲染（Windows: `winget install Gyan.FFmpeg`，macOS: `brew install ffmpeg`） |
| **Python 3.10+** | 运行全部脚本 |
| **faster-whisper** | 词级语音识别（首次运行自动下载模型，约 300MB-3GB，缓存于 `~/.cache/huggingface`） |
| **numpy** | 音频兴奋点检测 |

### 可选依赖（音色分离 / 多主播 PK 必需）

| 依赖 | 用途 |
|---|---|
| **torch + torchaudio** | 深度学习运行时（CPU 版即可，GPU 更快） |
| **pyannote.audio** | 说话人分离（`diarize.py`） |
| **HuggingFace token** | pyannote 模型是门控的：需注册 huggingface.co → 创建 token → 接受 [speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) 和 [segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) 模型许可 |

> 不装 torch 也能用全套其他功能：`diarize.py` 自动降级，所有句子标记为 `S0`（未分离说话人）。

### LLM 分析层（必须其一）

任意 **OpenAI 兼容端点**，环境变量配置：
```bash
export LLM_API_BASE="https://api.deepseek.com/v1"   # 或豆包/Kimi/GPT/Claude/通义/MiniMax/本地 vLLM…
export LLM_API_KEY="sk-..."
export LLM_MODEL="deepseek-chat"
```
分析质量直接受模型影响：**更强的模型 → 更准的高光判断**。推荐 DeepSeek-V3 / GPT-4o 级别模型。

### 配套剪辑工具（成片增强，可选）

| 工具 | 配合方式 |
|---|---|
| **video-use** | `edl.json` 的 `ranges` 结构兼容，二次精剪/去气口/加动效 |
| **剪映 jianying-editor** | `subtitles.srt` 直接 `import_srt(srt, track_name=...)` 导入，说话人标签自动保留 |
| **HyperFrames** | 切片文案转配音重制 + 弹入动效（中文科普解说风格） |
| **ffmpeg-video-effects** | 快速加转场/调色/特效字 |
| **yt-dlp** | 下载直播回放/长视频作为输入源 |

## ❓ FAQ

| 问题 | 解答 |
|---|---|
| 中文转写有错别字？ | 换 `--model large-v3`（small/medium 准确率有限）；正式发布务必用 large-v3 |
| 转写太慢？ | CPU 加 `--compute int8`；换 small 模型；有 GPU 用 `--device cuda` |
| pyannote 报 401 / 403？ | 没接受模型许可或 token 无读权限，见「可选依赖」 |
| 字幕说话人全是 S0？ | 没跑 `diarize.py`，或未安装 torch/pyannote |
| 高光判断不准？ | 确认 `--type` 选对切片类型；或换更强的 LLM 模型重跑 `analyze.py` |
| Windows 找不到 ffmpeg？ | 安装后重启终端；确认 ffmpeg.exe 在 PATH |
| 视频超过 2 小时？ | 用 `--start/--end` 分段转写，或先按章节粗切 |
| 能商用吗？ | 代码 MIT 协议可自由商用；但**切片内容版权归原直播者/平台**，发布前请确认授权（直播切片分销需获主播授权） |

## 📦 多 Agent 安装

| Agent | 位置 |
|---|---|
| Claude Code | `~/.claude/skills/video-clipper/` |
| Codex | `~/.codex/skills/video-clipper/` |
| OpenCode | `~/.config/opencode/skills/video-clipper/` |
| Hermes Agent | `~/AppData/Local/hermes/skills/ai-video/video-clipper/` |
| 任意 Agent | 把仓库目录指给 agent 即可 |

## 📁 目录结构

```
video-clipper/
├── SKILL.md              # 主文档：流程/问卷/硬规则/对接剪辑skill
├── prompts/              # LLM 分析模板（时间点定位/评分/标题）
├── references/           # 切片类型百科 + 安装说明
└── scripts/              # 全部 CLI 脚本
    ├── transcribe.py     # ASR
    ├── diarize.py        # 音色分离
    ├── build_timeline.py # 时间表 + SRT
    ├── audio_signal.py   # 兴奋点检测
    ├── analyze.py        # LLM 高光分析
    ├── cut.py            # 切割
    └── render.py         # 成片
```

## 🎯 高播放量分析输出示例

```json
{
  "start": 28.7, "end": 37.6,
  "type": "福利",
  "score": 0.95,
  "quote": "直接给你干到39块9，拍一送三",
  "reason": "价格反差炸裂，299干到39.9还送三件，福利感拉满必爆",
  "title": "299耳机今天只要39.9！拍一送三"
}
```

## 🔗 对接自动剪辑

- **video-use**：`edl.json` 的 `ranges` 结构兼容，可直接二次精剪/去气口/加动效
- **剪映 jianying-editor**：SRT 直接 `import_srt(srt, track_name=...)` 导入，字幕自带说话人标签
- **HyperFrames**：切片文案可转配音重制 + 弹入动效

## 📄 License

MIT © 2026 video-clipper contributors
