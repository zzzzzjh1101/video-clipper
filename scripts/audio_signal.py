#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_signal.py — 音频兴奋点检测（辅助信号，不是主判断）

检测:
  1. 高能段落（掌声/笑声/尖叫/欢呼/高亢情绪）→ type:"excite"
  2. 静音段落（可作切割点的候选）              → type:"silence"

原理: ffmpeg 输出 16kHz 单声道 PCM → numpy 计算滑动 RMS 能量，
      高能 = RMS 超过 全局均值+2σ；静音 = 归一化 RMS < 0.008。

用法:
  python audio_signal.py <video|audio> [--workdir clip_work]
输出:
  <workdir>/signals/<name>_audio_signal.json
  {"excite":[{start,end,level}], "silence":[{start,end}], "mean_rms":..., "std_rms":...}

说明: 这是给 LLM 分析层的**辅助证据**（比如某段文字恰好在高能区，
      大概率是笑点/高光）。真正的片段取舍由 analyze.py 结合文本判断。
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

RATE = 16000
WIN = 0.5       # 能量窗口 0.5s
HOP = 0.1       # 步进 0.1s


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def find_ffmpeg():
    from shutil import which
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = which(name)
        if p:
            return p
    raise SystemExit("找不到 ffmpeg")


def read_pcm(path):
    cmd = [find_ffmpeg(), "-i", path, "-vn", "-ac", "1", "-ar", str(RATE),
           "-f", "s16le", "pipe:1"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg 解码失败: {r.stderr[-500:]}")
    data = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return data


def compute_rms(data):
    win = int(WIN * RATE)
    hop = int(HOP * RATE)
    n = (len(data) - win) // hop + 1
    if n <= 0:
        return np.array([])
    idx = np.arange(win)[None, :] + (np.arange(n) * hop)[:, None]
    frames = data[idx]
    return np.sqrt(np.mean(frames ** 2, axis=1)), n * hop / RATE


def find_regions(mask, min_len_s, hop_s):
    """把布尔序列聚成连续区域，返回 [(start_s, end_s), ...]"""
    regions = []
    i = 0
    n = len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            dur = (j - i) * hop_s
            if dur >= min_len_s:
                regions.append((round(i * hop_s, 2), round(j * hop_s, 2)))
            i = j
        else:
            i += 1
    return regions


def main():
    ap = argparse.ArgumentParser(description="音频兴奋点检测")
    ap.add_argument("input", help="视频或音频文件")
    ap.add_argument("--workdir", default="clip_work")
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    workdir = os.path.join(os.path.dirname(src), args.workdir) if not os.path.isabs(args.workdir) else args.workdir
    sdir = os.path.join(workdir, "signals")
    os.makedirs(sdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    out_path = os.path.join(sdir, f"{base}_audio_signal.json")

    eprint("[audio_signal] 解码音频 ...")
    data = read_pcm(src)
    rms, hop_s = compute_rms(data)
    if rms.size == 0:
        raise SystemExit("音频过短或无法解码")

    mean_rms = float(np.mean(rms))
    std_rms = float(np.std(rms))
    excite_hi = mean_rms + 2.5 * std_rms
    excite_lo = mean_rms + 1.5 * std_rms

    # 高能（≥2.5σ）与中等（≥1.5σ）
    hi_mask = rms > excite_hi
    mid_mask = (rms > excite_lo) & (rms > 0.02)
    excite = []
    for s, e in find_regions(hi_mask, 0.6, hop_s):
        excite.append({"start": s, "end": e, "level": "high"})
    seen = set((x["start"], x["end"]) for x in excite)
    for s, e in find_regions(mid_mask, 1.0, hop_s):
        if (s, e) not in seen:
            excite.append({"start": s, "end": e, "level": "mid"})
    excite.sort(key=lambda x: x["start"])

    # 静音（归一化 RMS 很低，持续 ≥0.4s）→ 切割点候选
    silence_mask = rms < max(0.008, mean_rms * 0.15)
    silence = [{"start": s, "end": e} for s, e in find_regions(silence_mask, 0.4, hop_s)]

    doc = {"source": src, "excite": excite, "silence": silence,
           "mean_rms": round(mean_rms, 5), "std_rms": round(std_rms, 5)}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    eprint(f"[audio_signal] 高能段 {len(excite)} 处, 静音段 {len(silence)} 处")
    eprint(f"[audio_signal] 已写入 {out_path}")
    print(out_path)


if __name__ == "__main__":
    main()
