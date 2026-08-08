#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cut.py — 按 EDL 切割视频片段（词边界 + 30ms 音频淡入淡出）

用法:
  python cut.py <edl.json> [--outdir clip_work/clips] [--crf 20] [--preset fast]

EDL 结构（analyze.py 产出，兼容 video-use ranges）:
  {"sources": {"__MAIN__": "/path/video.mp4"},
   "ranges": [{"source":"__MAIN__","start":125.4,"end":152.8,"beat":"金句",
               "quote":"...","reason":"..."}]}

输出: <outdir>/NN_score_type.mp4 （NN=序号按评分排序）
硬规则:
  - 切点落在词/句边界（EDL 已由 analyze.py 对齐句子边界）
  - 每个切点 30ms afade 淡入淡出，杜绝爆音
  - 用 -ss 在 -i 之后（output seeking）+ 重编码，保证逐帧精确
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


def safe_name(s, maxlen=24):
    s = "".join(c for c in s if c not in '\\/:*?"<>|').strip()
    return s[:maxlen] or "clip"


def cut_one(ffmpeg, src, start, end, out, crf, preset):
    dur = end - start
    af = f"afade=t=in:st=0:d=0.03,afade=t=out:st={max(0.03, dur-0.03):.3f}:d=0.03"
    cmd = [ffmpeg, "-y", "-i", src, "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
           "-map", "0:v:0", "-map", "0:a:0",
           "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
           "-c:a", "aac", "-b:a", "192k", "-af", af,
           "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"切割失败 {out}: {r.stderr[-600:]}")


def main():
    ap = argparse.ArgumentParser(description="按 EDL 切割")
    ap.add_argument("edl", help="analyze.py 产出的 edl.json")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--preset", default="fast")
    args = ap.parse_args()

    with open(args.edl, "r", encoding="utf-8") as f:
        edl = json.load(f)

    sources = edl.get("sources", {})
    ranges = edl.get("ranges", [])
    if not sources or not ranges:
        raise SystemExit("EDL 缺少 sources 或 ranges")

    outdir = args.outdir
    if outdir is None:
        outdir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(args.edl)), "..", "clips"))
    os.makedirs(outdir, exist_ok=True)

    # 按评分排序（edl.ranges 已按分排序，这里直接编号）
    ffmpeg = find_ffmpeg()
    n = len(ranges)
    for i, rng in enumerate(ranges, 1):
        src = sources.get(rng["source"], "")
        if not src or not os.path.exists(src):
            raise SystemExit(f"找不到源视频: {src or rng.get('source')}")
        start, end = float(rng["start"]), float(rng["end"])
        if end <= start:
            eprint(f"[cut] 跳过非法区间 {start}-{end}")
            continue
        beat = safe_name(rng.get("beat", "clip"))
        out = os.path.join(outdir, f"{i:02d}_{start:06.1f}s_{beat}.mp4")
        eprint(f"[cut] ({i}/{n}) {start:.1f}-{end:.1f}s ({end-start:.1f}s) → {os.path.basename(out)}")
        cut_one(ffmpeg, src, start, end, out, args.crf, args.preset)

    eprint(f"[cut] 完成，共 {n} 条，输出目录: {outdir}")
    print(outdir)


if __name__ == "__main__":
    main()
