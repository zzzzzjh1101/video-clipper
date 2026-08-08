#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_timeline.py — 转写 JSON → 时间表 timeline.md + 字幕 subtitles.srt（带说话人）

用法:
  python build_timeline.py <transcript.json> [--with-speakers] [--outdir clip_work]
                           [--speaker-names "主播,连麦嘉宾"]

输出（同名 basename）:
  <outdir>/timeline/<name>_timeline.md    完整时间表（人工审阅/喂给 LLM 分析）
  <outdir>/timeline/<name>.srt            带说话人标签的字幕（[S0] 前缀）

--speaker-names: 逗号分隔，按 S0,S1,S2... 顺序映射成可读名字（如 主播,连麦嘉宾）。
"""
import argparse
import json
import os
import sys


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def fmt_ts(sec, srt=False):
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    if srt:
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"{h:02d}:{m:02d}:{s:02d}.{ms//100}{ms%100:02d}" if False else f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def build_md(doc, name, speaker_names):
    lines = []
    lines.append(f"# 时间表 — {name}")
    lines.append("")
    src = doc.get("source", "")
    dur = doc.get("duration")
    lines.append(f"- 源: `{src}`")
    if dur:
        lines.append(f"- 时长: {fmt_ts(dur)}")
    lines.append(f"- 模型: {doc.get('model', '?')} | 语言: {doc.get('language', '?')}")
    spk = sorted({s.get("speaker") for s in doc["segments"] if s.get("speaker")})
    if spk:
        lines.append(f"- 说话人: {', '.join(spk)} ({len(spk)} 人)")
    lines.append("")
    lines.append("## 时间表")
    lines.append("")
    lines.append("| 时间 | 说话人 | 内容 |")
    lines.append("|---|---|---|")
    for seg in doc["segments"]:
        t = f"{fmt_ts(seg['start'])}-{fmt_ts(seg['end'])}"
        sp = seg.get("speaker") or "S0"
        if speaker_names:
            idx = int(sp[1:]) if len(sp) > 1 and sp[1:].isdigit() else 0
            sp = speaker_names[idx] if idx < len(speaker_names) else sp
        text = seg["text"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {t} | {sp} | {text} |")
    return "\n".join(lines) + "\n"


def build_srt(doc, speaker_names):
    out = []
    idx = 1
    for seg in doc["segments"]:
        sp = seg.get("speaker") or "S0"
        if speaker_names:
            n = int(sp[1:]) if len(sp) > 1 and sp[1:].isdigit() else 0
            sp = speaker_names[n] if n < len(speaker_names) else sp
        text = seg["text"].strip()
        if not text:
            continue
        out.append(str(idx))
        out.append(f"{fmt_ts(seg['start'], srt=True)} --> {fmt_ts(seg['end'], srt=True)}")
        out.append(f"[{sp}] {text}")
        out.append("")
        idx += 1
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="生成时间表和字幕")
    ap.add_argument("transcript", help="transcribe.py / diarize.py 产出的 JSON")
    ap.add_argument("--with-speakers", action="store_true", help="显示说话人标签")
    ap.add_argument("--outdir", default="clip_work")
    ap.add_argument("--speaker-names", default=None, help='逗号分隔: "主播,连麦嘉宾"')
    args = ap.parse_args()

    with open(args.transcript, "r", encoding="utf-8") as f:
        doc = json.load(f)

    base = os.path.splitext(os.path.basename(args.transcript))[0]
    # 去掉 transcribe 的参数后缀（__model__lang__start__end）和 __diarized
    base = base.split("__")[0]
    names = [x.strip() for x in args.speaker_names.split(",")] if args.speaker_names else None

    workdir = args.outdir if os.path.isabs(args.outdir) else os.path.join(
        os.path.dirname(os.path.abspath(doc.get("source", "."))) or ".", args.outdir)
    tdir = os.path.join(workdir, "timeline")
    os.makedirs(tdir, exist_ok=True)

    md_path = os.path.join(tdir, f"{base}_timeline.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_md(doc, base, names if args.with_speakers else None))
    eprint(f"[timeline] 时间表: {md_path}")

    srt_path = os.path.join(tdir, f"{base}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(build_srt(doc, names if args.with_speakers else None))
    eprint(f"[timeline] 字幕: {srt_path}")
    print(md_path)
    print(srt_path)


if __name__ == "__main__":
    main()
