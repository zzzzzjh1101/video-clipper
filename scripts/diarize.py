#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diarize.py — 音色识别 / 说话人分离（多主播 PK、多人连麦）

用法:
  python diarize.py <video> --transcript <transcript.json> [--hf-token hf_xxx]
                    [--workdir clip_work]

依赖（可选）: torch + pyannote.audio，且需 HuggingFace token 并接受模型许可
  (见 references/install.md 方案A)。
无 torch/pyannote 时: 脚本明确报错并提示 --no-diarize 降级（所有句子归 S0），
  不影响其余流程。

输出: <workdir>/transcripts/<name>__diarized.json
  = 原 transcript 基础上每个 segment 增加 speaker 字段 (S0/S1/S2...)。
"""
import argparse
import json
import os
import subprocess
import sys


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def find_ffmpeg():
    from shutil import which
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = which(name)
        if p:
            return p
    raise SystemExit("找不到 ffmpeg")


def extract_audio(video, wav_path):
    cmd = [find_ffmpeg(), "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
           "-f", "wav", wav_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg 抽音频失败: {r.stderr[-500:]}")


def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers(segments, turns):
    """segments: 转写段列表; turns: [(start, end, label)] → 给每段分配说话人"""
    for seg in segments:
        best_label, best_ov = None, 0.0
        for ts, te, label in turns:
            ov = overlap(seg["start"], seg["end"], ts, te)
            if ov > best_ov:
                best_ov, best_label = ov, label
        if best_label is not None and best_ov > 0.05:
            seg["speaker"] = best_label
        else:
            seg["speaker"] = None
    return segments


def main():
    ap = argparse.ArgumentParser(description="音色分离")
    ap.add_argument("video", help="原始视频（用于提取音频）")
    ap.add_argument("--transcript", required=True, help="transcribe.py 产出的 JSON")
    ap.add_argument("--hf-token", default=None, help="HuggingFace token（或设环境变量 HF_TOKEN/PYANNOTE_AUTH_TOKEN）")
    ap.add_argument("--workdir", default="clip_work")
    args = ap.parse_args()

    try:
        import torch  # noqa
        from pyannote.audio import Pipeline
    except ImportError:
        raise SystemExit(
            "未安装 torch/pyannote.audio。\n"
            "  音色分离是可选功能。两种选择：\n"
            "  1) 跳过：继续用单说话人模式（所有句子标 S0），其他功能不受影响\n"
            "  2) 安装：见 references/install.md 方案A（pip install torch pyannote.audio + HF token）"
        )

    token = args.hf_token or os.environ.get("PYANNOTE_AUTH_TOKEN") or os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("需要 HuggingFace token：--hf-token hf_xxx 或环境变量 HF_TOKEN（见 install.md 方案A）")

    src = os.path.abspath(args.video)
    with open(args.transcript, "r", encoding="utf-8") as f:
        doc = json.load(f)

    out_path = args.transcript.replace(".json", "__diarized.json")
    if os.path.exists(out_path) and abs(os.path.getmtime(args.transcript) - os.path.getmtime(out_path)) < 5:
        eprint(f"[diarize] 缓存命中: {out_path}")
        print(out_path)
        return

    workdir = os.path.join(os.path.dirname(src), args.workdir) if not os.path.isabs(args.workdir) else args.workdir
    os.makedirs(os.path.join(workdir, "tmp"), exist_ok=True)
    wav = os.path.join(workdir, "tmp", os.path.basename(src) + "_diar.wav")
    if not os.path.exists(wav):
        eprint("[diarize] 提取音频 ...")
        extract_audio(src, wav)

    eprint("[diarize] 加载 pyannote/speaker-diarization-3.1 ...")
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                        use_auth_token=token)
    eprint("[diarize] 分离说话人（长视频需几分钟）...")
    diarization = pipeline(wav)
    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append((turn.start, turn.end, speaker))
    eprint(f"[diarize] 共 {len(turns)} 个语音段，{len(set(t for _, _, t in turns))} 个说话人")

    doc["segments"] = assign_speakers(doc["segments"], turns)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    eprint(f"[diarize] 已写入 {out_path}")
    print(out_path)


if __name__ == "__main__":
    main()
