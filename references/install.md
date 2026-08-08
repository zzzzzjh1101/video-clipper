# 环境安装说明（Windows / macOS / Linux）

## 必需

### 1. ffmpeg + ffprobe
```bash
# Windows（winget）
winget install Gyan.FFmpeg
# macOS
brew install ffmpeg
# Ubuntu
sudo apt install ffmpeg
```
验证：`ffmpeg -version`

### 2. Python 3.10+
建议用 uv 管理环境：
```bash
uv venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. faster-whisper（ASR 引擎）
```bash
pip install faster-whisper
# 国内加速
pip install faster-whisper -i https://pypi.tuna.tsinghua.edu.cn/simple
```
首次运行会自动下载模型（缓存到 `~/.cache/huggingface`）：
- `large-v3`（最准，中文推荐，CPU 需 int8）
- `medium`（平衡）
- `small`（快，适合草稿）

### 4. 其他 Python 依赖
```bash
pip install numpy
```

## 可选：音色分离（多主播 PK / 多人连麦必需）

### 方案 A：pyannote.audio（推荐，最准）
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121   # NVIDIA GPU
# 或 CPU 版
pip install torch torchaudio
pip install pyannote.audio

# 国内加速（torch 大文件走镜像）
pip install torch torchaudio -i https://pypi.tuna.tsinghua.edu.cn/simple
```
还需要 HuggingFace token（pyannote 模型是门控的）：
1. 注册 https://huggingface.co ，创建 token（读权限）
2. 接受模型许可：
   - https://huggingface.co/pyannote/speaker-diarization-3.1 （点 Accept）
   - https://huggingface.co/pyannote/segmentation-3.0 （点 Accept）
3. 设置环境变量：`export HF_TOKEN=hf_xxx`
4. 运行 `diarize.py --hf-token hf_xxx`（或设 `PYANNOTE_AUTH_TOKEN`）

### 方案 B：whisperx（转写+分离一体，也需要 torch + pyannote 模型）
```bash
pip install whisperx
```
whisperx 会额外下载对齐模型和 diarization 模型，同样需要接受 pyannote 许可。

### 方案 C：不装 torch（降级）
无 torch 时 `diarize.py` 自动跳过，时间表里所有句子归为 `S0`（未分离）。
**其余全部功能不受影响** —— 转写、时间表、高光分析、切割、成片照常。

## LLM 分析层（高光打分 / 爆点标注）

任意 OpenAI 兼容端点，环境变量：
```bash
export LLM_API_BASE="https://api.deepseek.com/v1"      # 或豆包/Kimi/通义/MiniMax/本地 vLLM…
export LLM_API_KEY="sk-..."
export LLM_MODEL="deepseek-chat"
```
本机（2026）可直接用：
- DeepSeek：key 在 `~/AppData/Local/hermes/.env`
- MiniMax 国内版：`MINIMAX_CN_API_KEY`，base=`https://api.minimaxi.com/v1`，模型 `MiniMax-M3`

## 验证安装

```bash
python -c "import faster_whisper; print('ASR OK')"
python scripts/transcribe.py --help
ffmpeg -version | head -1
```
音色分离验证：
```bash
python -c "import torch, pyannote.audio; print('diarization OK')"
```

## 常见坑

| 问题 | 解决 |
|---|---|
| whisper 下载慢/失败 | 设 `HF_ENDPOINT=https://hf-mirror.com`（国内镜像） |
| CPU 转写慢 | 用 `--model small --compute int8`；长视频分段（whisper 自动分段） |
| pyannote 报 401 | 没接受模型许可或 token 无读权限，见方案 A |
| GPU 显存不足 | `--model medium` + `--compute int8`；或设 `--device cpu` |
| Windows 上 ffmpeg 找不到 | 重启终端；确认 ffmpeg.exe 在 PATH |
| 视频太长（>2h） | 先 `cut.py` 按章节粗切，或只转写指定时间段（`--start --end`） |
