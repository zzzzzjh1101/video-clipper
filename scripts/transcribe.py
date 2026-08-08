#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcribe.py — 视频/音频 → 词级 ASR 转写 JSON（缓存）

用法:
  python transcribe.py <input> [--model large-v3] [--language zh] [--device auto]
                       [--compute int8] [--start S] [--end E] [--workdir clip_work]

输出:
  <workdir>/transcripts/<basename>__<model>__<lang>.json
  结构: {source, source_mtime, model, language, duration, segments:[
          {id, start, end, text, words:[{word,start,end}], speaker:null}]}

缓存: 源文件 mtime 未变 + 同参数 → 直接复用，不重转写。
"""
import argparse
import json
import os
import subprocess
import sys
import time


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def find_ffmpeg():
    for name in ("ffmpeg", "ffmpeg.exe"):
        from shutil import which
        p = which(name)
        if p:
            return p
    raise SystemExit("找不到 ffmpeg，请先安装并加入 PATH（见 references/install.md）")


def extract_audio(video, wav_path, start=None, end=None):
    """抽 16kHz 单声道 wav（faster-whisper 的标准输入格式）"""
    cmd = [find_ffmpeg(), "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-f", "wav", wav_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg 抽音频失败: {r.stderr[-800:]}")
    return wav_path


def transcribe(wav_path, model_size, language, device, compute_type,
               start=None, end=None):
    from faster_whisper import WhisperModel
    eprint(f"[transcribe] 加载模型 {model_size} (device={device}, compute={compute_type}) ...")
    t0 = time.time()
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    eprint(f"[transcribe] 模型就绪 {time.time()-t0:.1f}s，开始识别 ...")
    kwargs = dict(word_timestamps=True, vad_filter=True, beam_size=5)
    if language:
        kwargs["language"] = language
    if start is not None or end is not None:
        # faster-whisper 支持 offset_seconds 直接跳过，但为保证与视频时间轴一致，
        # 已用 ffmpeg 裁剪；记录裁剪偏移以便还原时间轴。
        pass
    segments, info = model.transcribe(wav_path, **kwargs)
    out_segs = []
    for i, s in enumerate(segments):
        words = []
        for w in (s.words or []):
            words.append({"word": w.word, "start": round(w.start, 3), "end": round(w.end, 3)})
        out_segs.append({
            "id": i,
            "start": round(s.start, 3),
            "end": round(s.end, 3),
            "text": s.text.strip(),
            "words": words,
            "speaker": None,
        })
    eprint(f"[transcribe] 完成: {len(out_segs)} 段, 用时 {time.time()-t0:.1f}s")
    return out_segs, info.duration


def main():
    ap = argparse.ArgumentParser(description="词级 ASR 转写")
    ap.add_argument("input", help="视频/音频文件")
    ap.add_argument("--model", default="large-v3", help="模型大小: tiny/base/small/medium/large-v3")
    ap.add_argument("--language", default="zh")
    ap.add_argument("--device", default="auto", help="auto/cpu/cuda")
    ap.add_argument("--compute", default=None, help="int8/float16/float32（默认: cuda→float16, cpu→int8）")
    ap.add_argument("--start", type=float, default=None)
    ap.add_argument("--end", type=float, default=None)
    ap.add_argument("--workdir", default="clip_work", help="工作目录（默认 clip_work/）")
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        raise SystemExit(f"文件不存在: {src}")

    compute = args.compute
    if compute is None:
        compute = "float16" if args.device == "cuda" else "int8"

    workdir = os.path.join(os.path.dirname(src), args.workdir) if not os.path.isabs(args.workdir) else args.workdir
    tdir = os.path.join(workdir, "transcripts")
    os.makedirs(tdir, exist_ok=True)
    tmpdir = os.path.join(workdir, "tmp")
    os.makedirs(tmpdir, exist_ok=True)

    base = os.path.splitext(os.path.basename(src))[0]
    cache_key = f"{base}__{args.model}__{args.language}__{args.start}__{args.end}"
    out_path = os.path.join(tdir, cache_key + ".json")
    mtime = os.path.getmtime(src)

    # 缓存命中
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if abs(cached.get("source_mtime", -1) - mtime) < 1:
                eprint(f"[transcribe] 缓存命中: {out_path}")
                print(out_path)
                return
        except Exception:
            pass

    wav = os.path.join(tmpdir, cache_key + ".wav")
    extract_audio(src, wav, args.start, args.end)
    segs, dur = transcribe(wav, args.model, args.language, args.device, compute,
                           args.start, args.end)

    doc = {
        "source": src,
        "source_mtime": mtime,
        "model": args.model,
        "language": args.language,
        "duration": round(dur, 3) if dur else None,
        "offset": args.start or 0.0,
        "segments": segs,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    eprint(f"[transcribe] 已写入 {out_path}")
    # 清理临时 wav
    try:
        os.remove(wav)
    except OSError:
        pass
    print(out_path)


if __name__ == "__main__":
    main()
