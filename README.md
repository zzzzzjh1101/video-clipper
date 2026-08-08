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
