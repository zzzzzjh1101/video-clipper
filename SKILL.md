---
name: video-clipper
description: Use when 直播/长视频自动切片：ASR转写、音色分离(说话人)、LLM高光分析、时间表、带说话人字幕、ffmpeg切割、对接剪辑skill出成片。多agent通用。
---

# Video Clipper · 视频切片（直播切片 / 长视频切片）

把一段直播回放或长视频，自动变成 **「带时间表的字幕 + 高光爆点标注」→ 切成多条短视频 → 配合剪辑 skill 出成片**。
面向：自媒体创作者、直播切片号、二创作者、运营。

## 这个 skill 能做什么

| 能力 | 产出物 |
|---|---|
| 语音识别（ASR） | 词级时间戳转写 JSON（缓存） |
| 音色识别 / 说话人分离（多主播 PK、多人连麦） | 每句话带 `[S0]/[S1]/[S2]` 说话人标签 |
| 自主切片模式 | `timeline.md` 完整时间表 + `highlights.json` 高光时间点 |
| 高播放量分析 | 每个候选片段标注「爆点类型 + 评分 + 推荐理由 + 起止时间」 |
| 带时间表的字幕文件 | `subtitles.srt`（含说话人标签） |
| 自动切割 | ffmpeg 按高光 EDL 切成多条短视频（词边界 + 淡入淡出） |
| 自动成片 | 对接 video-use / jianying-editor / hyperframes / ffmpeg-video-effects 出最终成片 |

## 多 agent / 多模型支持（开箱即用）

本 skill 是 **纯 Markdown 流程 + 纯 Python CLI**，不依赖任何特定 agent 框架，任何能读文件的 agent 都能用：

- **Claude Code** → 放 `~/.claude/skills/video-clipper/`
- **Codex** → 放 `~/.codex/skills/video-clipper/`
- **OpenCode** → 放 `~/.config/opencode/skills/video-clipper/`
- **Hermes Agent** → 放 `~/AppData/Local/hermes/skills/ai-video/video-clipper/`
- **通用** → 任何路径，在对话里贴 SKILL.md 或指向该目录即可

LLM 分析层走 **OpenAI 兼容 API**，主流模型都能接（DeepSeek / 豆包 / Kimi / GPT / Claude / 通义 / GLM / MiniMax……）：
```bash
export LLM_API_BASE="https://api.deepseek.com/v1"   # 任意 OpenAI 兼容端点
export LLM_API_KEY="sk-..."
export LLM_MODEL="deepseek-chat"
```
本机已验证可用的分析模型（2026）：DeepSeek V3（`.env` 已有 key）、MiniMax-M3（`MINIMAX_CN_API_KEY`，base=`https://api.minimaxi.com/v1`）。

## 三种运行模式

1. **交互模式（默认）**：agent 先按问卷提问，确认切片类型和参数后再执行。
2. **自主模式**：用户给「视频 + 类型 + 平台」就说 `全自动`，agent 跳过提问直接跑完五步流程。
3. **半自动模式**：只产出时间表和字幕，人工勾选片段后再切（适合对高光判断有自己标准的创作者）。

## 问卷 —— agent 执行前自动提问（问题随材料调整，非固定清单）

拿到视频后 agent 先 `ffprobe` + 抽样转写开头 30 秒，再问：

1. **素材属于哪类切片？**（决定用哪套分析 prompt，见「切片类型百科」）
   - 电商带货 / 娱乐综艺 / 游戏高光 / 知识干货 / 观点输出 / 演讲口播 / 故事剧情 / 才艺表演 / 直播互动(连麦·PK·PK连麦) / 产品体验 / 内容评测 / 情感陪伴 / 新闻资讯
   - 不确定 → agent 从转写内容推断并让用户确认
2. **目标切片时长？** 15-30s（纯引流） / 30-60s（常规） / 1-3min（内容型） / 3-6min（知识长片段）
3. **发布平台 / 画幅？** 抖音快手 9:16 / B站 YouTube 16:9 / 视频号 1:1 / 多平台（出多画幅）
4. **几个人说话？** 单人 / 双人 PK / 多人连麦（≥3）→ 决定是否跑音色分离
5. **要什么输出？** 只要时间表 / 时间表+字幕 / 直接切片段 / 完整成片（含字幕动效）
6. **高光标准偏好？** 默认全类型评估；可指定：只要金句 / 只要高能场面 / 只要干货 / 只要争议冲突 / 只要情绪爆点

## 核心流程（五步）

```
输入视频/直播回放
   │
   ▼ ① transcribe.py     ffmpeg 抽 16kHz wav → faster-whisper 词级 ASR → transcripts/<name>.json（缓存）
   │
   ▼ ② diarize.py        （多人场景）pyannote 音色分离 → 句子打 S0/S1/S2… 标签（无 torch 时自动跳过）
   │
   ▼ ③ audio_signal.py   （可选）能量/兴奋点检测：笑声、掌声、尖叫、高能段落（辅助 LLM 判断）
   │
   ▼ ④ analyze.py        LLM 按「切片类型 prompt」读时间表 → highlights.json / edl.json
   │                       （高光时间点 + 爆点类型 + 评分 0-1 + 推荐理由 + 标题）
   │
   ▼ ⑤ 产出              timeline.md（时间表） + subtitles.srt（带说话人）→ 用户确认
   │
   ▼ ⑥ cut.py            按 EDL 词边界切割 → clips/*.mp4（30ms 淡入淡出）
   │
   ▼ ⑦ 成片              对接剪辑 skill：字幕 / 动效 / BGM / 封面帧 → final/*.mp4
```

**每步的产物都落到 `<素材目录>/clip_work/` 下，源文件不动。**

## 目录结构

```
video-clipper/
├── SKILL.md
├── prompts/
│   ├── timepoints.md     # 高光时间点定位（按类型变体）
│   ├── score.md          # 爆点评分 + 推荐理由
│   └── title.md          # 切片标题生成
├── references/
│   ├── clip-types.md     # 切片类型百科（判定特征、切法策略）
│   └── install.md        # 环境安装（faster-whisper / pyannote / ffmpeg）
└── scripts/
    ├── transcribe.py     # ASR：视频 → 词级转写 JSON
    ├── diarize.py        # 音色分离：转写 JSON → 带说话人标签
    ├── build_timeline.py # 转写 → timeline.md + SRT（可选 --with-speakers）
    ├── audio_signal.py   # 音频兴奋点检测（能量/掌声/笑声）
    ├── analyze.py        # LLM 高光分析 → highlights.json + edl.json
    ├── cut.py            # EDL → ffmpeg 切割成片段
    └── render.py         # 片段 → 成片（字幕烧录/拼接，或转交其他剪辑 skill）
```

## 命令行接口速查

```bash
# ① 转写（--model 按机器性能：large-v3 最准；中文默认 zh；CPU 用 int8）
python scripts/transcribe.py input.mp4 --model large-v3 --language zh

# ② 音色分离（多人 PK/连麦；需先装 pyannote，见 references/install.md）
python scripts/diarize.py input.mp4 --transcript transcripts/input.json --hf-token <HF_TOKEN>

# ③ 时间表 + 字幕（--with-speakers 用 diarize 结果）
python scripts/build_timeline.py transcripts/input.json --with-speakers

# ④ LLM 高光分析（--type 必填：ecommerce|entertainment|game|knowledge|opinion|speech|story|talent|live_interaction|experience|review|emotion|news）
python scripts/analyze.py timeline.md --type knowledge --llm-base $LLM_API_BASE --llm-key $LLM_API_KEY --llm-model $LLM_MODEL

# ⑤ 切割（edl.json 由 analyze.py 产出）
python scripts/cut.py edl.json --outdir clips/

# ⑥ 成片（可选：直出带字幕竖版；复杂成片转交 video-use / jianying-editor）
python scripts/render.py clips/ --format 9:16 --subtitles subtitles.srt -o final/
```

## 硬规则（违反即出错）

1. **词边界切割**：切点必须落在 whisper 词时间戳边界上，绝不切断音节/字（`cut.py` 自动做，手写 EDL 时 agent 也要遵守）。
2. **30ms 音频淡入淡出**：每个切点 `afade` 0.03s，否则有爆音。
3. **字幕最后加**：先叠效果再烧字幕（沿用 video-use 的 Rule 1）。
4. **转写缓存**：源文件不变就永不重转写；换模型参数才重跑。
5. **高光时间点必须落在句子/语义边界**：以转写文本为准，不硬切。
6. **字幕文本用转写原文**，不做「美化改写」；错别字修正要逐字对比。
7. **时长紧凑**：切片宁短勿长，钩子前 3 秒必须有爆点（平台完播率法则）。
8. **ASR 词级模式**：禁用 SRT/句子级模式做分析，丢失亚秒级边界。
9. **不在源目录写东西**：一切产物进 `clip_work/`。
10. **先出时间表再动手切**：自主模式也要先生成 `timeline.md` 给用户过目（除非用户明确说直接出片）。

## 高播放量分析（爆点标注）

`analyze.py` 让 LLM 对每个候选片段按四维打分（0-1），并给出爆点类型和理由：

- **信息价值**：独特见解 / 信息密度 / 实用干货
- **情感共鸣**：喜悦、愤怒、好奇、共鸣、爽感
- **传播潜力**：金句、梗、争议、可讨论性
- **结构完整**：有始有终、起承转合

输出（edl.json）每项：
```json
{
  "source": "input.mp4",
  "start": 125.4, "end": 152.8,
  "type": "金句",                 // 爆点类型：金句|高能|干货|争议|情绪|名场面|福利|剧情转折…
  "score": 0.92,                 // 爆款潜力分
  "quote": "这句话就是原话……",
  "reason": "15字-30字推荐理由",
  "title": "切片标题（30字内）",
  "speakers": ["S1"]
}
```

## 切片类型百科（摘要，详见 references/clip-types.md）

| 类型 | 切什么 | 典型时长 | 判定特征 |
|---|---|---|---|
| 电商带货 ecommerce | 商品卖点、价格福利、逼单话术 | 15-45s | 「上链接」「福利」「XX到手价」 |
| 娱乐综艺 entertainment | 笑点、名场面、游戏环节 | 20-60s | 笑声、起哄、反转 |
| 游戏高光 game | 五杀、翻盘、极限操作 | 15-40s | 击杀音效、解说高亢 |
| 知识干货 knowledge | 方法论、信息差、案例 | 1-4min | 「记住/核心/其实」 |
| 观点输出 opinion | 鲜明观点、争议话题、金句 | 30-90s | 「我觉得/凭什么/就是」 |
| 演讲口播 speech | 金句、情绪高潮、号召 | 20-60s | 排比、停顿、升调 |
| 故事剧情 story | 悬念、转折、揭晓 | 30-90s | 「结果/没想到/后来」 |
| 才艺 talent | 高光段落、绝活 | 15-45s | 音乐高潮、欢呼 |
| 直播互动 live_interaction | 连麦、PK、吵架、打赏瞬间 | 20-60s | 双人以上对话、情绪冲突 |
| 产品体验 experience | 开箱、使用痛点、真实反馈 | 30-90s | 「我用了/真的/踩坑」 |
| 内容评测 review | 对比、结论、榜单 | 30-120s | 「对比/总结/推荐」 |
| 情感陪伴 emotion | 走心语录、深夜电台 | 20-60s | 慢节奏、音乐、低语 |
| 新闻资讯 news | 事件核心、关键信息 | 15-45s | 事件描述、时间地点 |

## 对接自动剪辑 skill（出成片）

切出来的 `clips/*.mp4` + `subtitles.srt` 按需转交：

- **video-use**（精剪/去气口/加动效）：把 clips 目录丢给它，用 `takes_packed.md` 思路做二次精剪。
- **jianying-editor**（剪映工程）：`project.script.import_srt(srt, track_name=...)` 直接导入带说话人的 SRT（见 jianying-editor skill）。
- **hyperframes / hyperframes-cn-video**（中文科普解说风）：切片文案 + edge-tts 配音重制，加弹入动效。
- **ffmpeg-video-effects**：快速加字幕/转场/调色。

## 安装

环境要求：Python 3.10+、ffmpeg（含 ffprobe）、faster-whisper。音色分离需 torch + pyannote（可选）。
详见 `references/install.md`（含国内镜像加速、HF token 说明）。

## 典型会话示例（agent 应这样开场）

> 用户：帮我切这场直播
> agent：好。我先转写前 30 秒看看内容 → 【问卷】这是游戏直播还是带货？目标多长？发抖音（9:16）吗？就你一个人讲还是有连麦？
> 用户：带货的，30 秒内，抖音，我一个人讲
> agent：【跑 ①transcribe → ③timeline → ④analyze --type ecommerce】这是时间表和 8 个高光候选，最火的是 12:35 那句「今天直接给你干到 39 块 9」（评分 0.94，逼单福利型）。切哪几条？
