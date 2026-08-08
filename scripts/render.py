#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — 切片 → 成片（画幅转换 + 字幕烧录 + 可选拼接）

用法:
  python render.py <clips_dir|clip.mp4> [--format 9:16|16:9|1:1] [--subtitles <srt>]
                   [--offset <源视频起始时间秒>] [--concat] [-o final/]

说明:
  - 字幕烧录按切片在源视频中的偏移自动重排（subtitles filter 需要切片内时间轴）。
  - --offset: 若切片来自源视频某段（cut.py 输出自带原名时间戳，自动推断），
    也可手动指定；多片段各自推断。
  - 复杂成片（动效/转场/BGM/多轨）转交 video-use / jianying-editor / hyperframes。
输出: final/ 下同名文件；--concat 时输出 final/concat.mp4
"""
import argparse
import os
import re
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


def parse_srt(path):
    """srt → [(start_s, end_s, text)]"""
    out = []
    with open(path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    blocks = re.split(r"\n\s*\n", content.strip())
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 2:
            continue
        m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})", lines[1])
        if not m:
            continue
        def ts(h, mi, s, ms):
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000
        start = ts(m.group(1), m.group(2), m.group(3), m.group(4))
        end = ts(m.group(5), m.group(6), m.group(7), m.group(8))
        text = "\n".join(lines[2:])
        out.append((start, end, text))
    return out


def offset_srt(src_srt, offset, out_srt):
    """把 SRT 整体平移 -offset 秒（切片内时间轴），丢弃负时间条目"""
    entries = parse_srt(src_srt)
    with open(out_srt, "w", encoding="utf-8") as f:
        idx = 1
        for start, end, text in entries:
            s, e = start - offset, end - offset
            if e <= 0.3:
                continue
            s = max(0.0, s)
            def ts(sec):
                h = int(sec // 3600); m = int((sec % 3600) // 60)
                s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
                if ms >= 1000: ms = 999
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            f.write(f"{idx}\n{ts(s)} --> {ts(e)}\n{text}\n\n")
            idx += 1
    return out_srt


def infer_offset(filename):
    """从 cut.py 命名 01_0125.4s_金句.mp4 推断源视频偏移"""
    m = re.search(r"_(\d{3,6})\.(\d)s_", filename)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 10.0
    return 0.0


def vf_for(fmt, srt_path=None):
    if fmt == "9:16":
        vf = "crop=min(iw\\,ih*9/16):ih,scale=1080:1920:flags=lanczos"
    elif fmt == "1:1":
        vf = "crop=min(iw\\,ih):min(iw\\,ih),scale=1080:1080:flags=lanczos"
    else:
        vf = "scale=1920:1080:flags=lanczos"
    if srt_path:
        vf += f",subtitles='{srt_path.replace(os.sep, '/')}'"
    return vf


def process_one(ffmpeg, clip, fmt, sub_entries, offset, out_path):
    srt_for_clip = None
    if sub_entries:
        srt_for_clip = out_path + ".tmp.srt"
        offset_srt(sub_entries, offset, srt_for_clip)
    vf = vf_for(fmt, srt_for_clip)
    cmd = [ffmpeg, "-y", "-i", clip, "-vf", vf, "-c:v", "libx264", "-crf", "20",
           "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart", out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if srt_for_clip and os.path.exists(srt_for_clip):
        try:
            os.remove(srt_for_clip)
        except OSError:
            pass
    if r.returncode != 0:
        raise SystemExit(f"渲染失败 {out_path}: {r.stderr[-600:]}")


def main():
    ap = argparse.ArgumentParser(description="切片→成片")
    ap.add_argument("input", help="clips 目录或单个 mp4")
    ap.add_argument("--format", default="9:16", choices=["9:16", "16:9", "1:1"])
    ap.add_argument("--subtitles", default=None, help="源时间轴 SRT（自动按切片偏移）")
    ap.add_argument("--offset", type=float, default=None, help="手动指定偏移秒")
    ap.add_argument("--concat", action="store_true", help="拼接所有片段为一条")
    ap.add_argument("-o", "--outdir", default="final")
    args = ap.parse_args()

    if os.path.isdir(args.input):
        clips = sorted(f for f in os.listdir(args.input) if f.lower().endswith((".mp4", ".mov", ".mkv")))
        clips = [os.path.join(args.input, c) for c in clips]
    else:
        clips = [args.input]
    if not clips:
        raise SystemExit(f"没有找到视频: {args.input}")

    sub_entries = args.subtitles if args.subtitles and os.path.exists(args.subtitles) else None
    os.makedirs(args.outdir, exist_ok=True)
    ffmpeg = find_ffmpeg()

    done = []
    for clip in clips:
        offset = args.offset if args.offset is not None else infer_offset(os.path.basename(clip))
        out = os.path.join(args.outdir, os.path.basename(clip))
        eprint(f"[render] {os.path.basename(clip)} (offset={offset:.1f}s, {args.format})")
        process_one(ffmpeg, clip, args.format, sub_entries, offset, out)
        done.append(out)

    if args.concat and len(done) > 1:
        listfile = os.path.join(args.outdir, "concat.txt")
        with open(listfile, "w", encoding="utf-8") as f:
            for d in done:
                f.write(f"file '{d.replace(os.sep, '/')}'\n")
        concat_out = os.path.join(args.outdir, "concat.mp4")
        r = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", listfile,
                            "-c", "copy", concat_out], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"拼接失败: {r.stderr[-500:]}")
        eprint(f"[render] 拼接完成: {concat_out}")
        done.append(concat_out)
        try:
            os.remove(listfile)
        except OSError:
            pass

    eprint(f"[render] 完成，共 {len(done)} 个文件 → {args.outdir}")
    print(args.outdir)


if __name__ == "__main__":
    main()
