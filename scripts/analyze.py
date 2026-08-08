#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze.py — LLM 高光分析：时间表 → 高光 EDL（爆点类型 + 评分 + 理由 + 标题）

用法:
  python analyze.py <timeline.md> --type <类型> [--llm-base URL] [--llm-key KEY]
                     [--llm-model MODEL] [--max-clips 12] [--target-dur 30]
                     [--signal <audio_signal.json>] [--outdir clip_work]

类型 --type: ecommerce|entertainment|game|knowledge|opinion|speech|story|
             talent|live_interaction|experience|review|emotion|news

LLM 配置: 优先 --llm-* 参数，否则环境变量 LLM_API_BASE / LLM_API_KEY / LLM_MODEL
          （OpenAI 兼容端点，DeepSeek/豆包/Kimi/GPT/Claude/通义/MiniMax 均可）

输出:
  <outdir>/highlights/<name>_highlights.json   完整高光列表（含评分/理由/标题）
  <outdir>/highlights/<name>_edl.json          切割用 EDL（兼容 video-use 的 ranges 结构）

时间对齐: 所有 start/end 会被吸附到时间表中最近的句子边界，绝不硬切。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompts", "timepoints.md")

TYPE_RULES = {
    "ecommerce": (
        "· 切：核心卖点、价格机制（到手价/券/拍N发N）、逼单话术、使用效果、福利氛围\n"
        "· 起：卖点抛出句；止：价格/逼单收尾句（必须包含价格信息）\n"
        "· 目标 15-45s；字幕放大价格数字的片段优先给高分\n"
        "· 删：寒暄、欢迎词、与商品无关的闲聊"),
    "entertainment": (
        "· 切：笑点完整闭环（铺垫→爆发→反应）、名场面、游戏环节高潮、互动火花、翻车\n"
        "· 起：笑点铺垫前 1-2s；止：观众/嘉宾反应结束（笑声就是爆点的一部分）\n"
        "· 绝不在笑点中间切断；目标 20-60s"),
    "game": (
        "· 切：五杀/团灭、极限反杀、翻盘、天秀操作、高能语音互动\n"
        "· 起：操作开始前 1-2s；止：结算/反应结束，保留击杀音效段落\n"
        "· 目标 15-40s；高能区（信号文件 excite 区）与文本重合处加分"),
    "knowledge": (
        "· 切：方法论、信息差、反常识、案例拆解、避坑、步骤教学\n"
        "· 起：观点/结论抛出句；止：论证闭环（一条切片一个知识点）\n"
        "· 目标 1-3min 可接受；钩子前置：先结论后论证；字幕整句完整"),
    "opinion": (
        "· 切：鲜明观点、争议话题、犀利吐槽、金句、站队表态\n"
        "· 起：观点首发句；止：金句收尾（论证链完整）\n"
        "· 目标 30-90s；争议度高的给高分（吃瓜属性=流量）"),
    "speech": (
        "· 切：金句、排比高潮、情绪爆发、号召结尾、动人故事片段\n"
        "· 起：蓄力开始；止：金句落地+掌声/反应\n"
        "· 目标 20-60s；排比句、升调处优先"),
    "story": (
        "· 切：悬念、转折、揭晓、高潮冲突、结尾反转\n"
        "· 起：转折前留钩子；止：揭晓完整；可断在悬念处（引导看全集）\n"
        "· 目标 30-90s"),
    "talent": (
        "· 切：高光段落（副歌/绝活/大招）、观众反应、救场\n"
        "· 起：高光前 1s；止：表演结束+欢呼收尾\n"
        "· 目标 15-45s；音乐高潮处优先"),
    "live_interaction": (
        "· 切：连麦爆点、PK 名场面（反超/惩罚）、吵架对峙、打赏感恩、粉丝互动高能\n"
        "· 起：冲突/话题引入；止：交锋结束，双方发言都保留完整+反应声\n"
        "· 目标 20-60s；多说话人，speakers 列出全部；冲突张力大的给高分"),
    "experience": (
        "· 切：开箱、使用痛点、效果对比、踩坑吐槽、真实反馈\n"
        "· 起：痛点抛出；止：结论/建议；删冗长过程\n"
        "· 目标 30-90s；共鸣感强的优先"),
    "review": (
        "· 切：对比结论、榜单、避雷/推荐、参数解读\n"
        "· 起：结论先行句；止：关键论据说完；删测试过程\n"
        "· 目标 30-120s"),
    "emotion": (
        "· 切：走心语录、深夜独白、情感故事、治愈瞬间\n"
        "· 起：情绪进入；止：金句落地；保留呼吸和停顿\n"
        "· 目标 20-60s；慢节奏段落优先"),
    "news": (
        "· 切：事件核心、关键信息、权威表态、现场画面\n"
        "· 起：事件描述首句；止：信息完整段落；不加工不加戏\n"
        "· 目标 15-45s；注明信息点"),
}

TYPE_NAMES = {
    "ecommerce": "电商带货", "entertainment": "娱乐综艺", "game": "游戏高光",
    "knowledge": "知识干货", "opinion": "观点输出", "speech": "演讲口播",
    "story": "故事剧情", "talent": "才艺表演", "live_interaction": "直播互动(连麦/PK)",
    "experience": "产品体验", "review": "内容评测", "emotion": "情感陪伴", "news": "新闻资讯",
}


def eprint(*a):
    print(*a, file=sys.stderr, flush=True)


def read_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def call_llm(base, key, model, messages, max_tokens=8000, temperature=0.3):
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise SystemExit(f"LLM 调用失败: {e}")
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise SystemExit(f"LLM 返回格式异常: {str(data)[:500]}")


def extract_json(text):
    """容错提取 JSON：剥掉 markdown 代码块、前后废话"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    m = re.search(r"(\{.*\})", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        raise SystemExit(f"LLM 输出不是合法 JSON:\n{text[:800]}")


def parse_timeline_segments(timeline_path):
    """从 timeline.md 解析句子边界 [(start, end, speaker, text)]"""
    segs = []
    pat = re.compile(r"^\|\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})-(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*\|\s*(\S+)\s*\|\s*(.*?)\s*\|$")
    with open(timeline_path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.strip())
            if not m:
                continue
            def ts(h, mi, s, ms):
                return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000
            start = ts(m.group(1), m.group(2), m.group(3), m.group(4))
            end = ts(m.group(5), m.group(6), m.group(7), m.group(8))
            segs.append({"start": start, "end": end, "speaker": m.group(9), "text": m.group(10)})
    if not segs:
        raise SystemExit(f"无法从 {timeline_path} 解析时间表（先跑 build_timeline.py）")
    return segs


def align(start, end, segs):
    """吸附到最近的句子边界"""
    best_s, best_e = None, None
    # start → 最近的句子起点
    cands = sorted([(abs(s["start"] - start), s["start"]) for s in segs])
    best_s = cands[0][1]
    # end → 最近的句子终点（必须 > best_s）
    cands = sorted([(abs(s["end"] - end), s["end"]) for s in segs if s["end"] > best_s + 0.3])
    if cands:
        best_e = cands[0][1]
    else:
        best_e = max(s["end"] for s in segs)
    if best_e - best_s < 1.0:
        # 兜底：找包含该区间的完整句子
        for s in segs:
            if s["start"] <= start and s["end"] >= end:
                return s["start"], s["end"]
        best_e = best_s + 3.0
    return round(best_s, 3), round(best_e, 3)


def main():
    ap = argparse.ArgumentParser(description="LLM 高光分析")
    ap.add_argument("timeline", help="build_timeline.py 产出的 timeline.md")
    ap.add_argument("--type", required=True, choices=list(TYPE_RULES.keys()), help="切片类型")
    ap.add_argument("--llm-base", default=os.environ.get("LLM_API_BASE"))
    ap.add_argument("--llm-key", default=os.environ.get("LLM_API_KEY"))
    ap.add_argument("--llm-model", default=os.environ.get("LLM_MODEL"))
    ap.add_argument("--max-clips", type=int, default=12)
    ap.add_argument("--target-dur", type=int, default=30, help="目标时长秒")
    ap.add_argument("--signal", default=None, help="audio_signal.py 输出（可选辅助）")
    ap.add_argument("--outdir", default="clip_work")
    args = ap.parse_args()

    if not (args.llm_base and args.llm_key and args.llm_model):
        raise SystemExit("需要 LLM 配置：--llm-base/--llm-key/--llm-model 或环境变量 LLM_API_BASE/LLM_API_KEY/LLM_MODEL")

    segs = parse_timeline_segments(args.timeline)
    timeline_text = open(args.timeline, "r", encoding="utf-8").read()
    if args.signal and os.path.exists(args.signal):
        sig = json.load(open(args.signal, encoding="utf-8"))
        if sig.get("excite"):
            timeline_text += "\n\n## 音频兴奋点辅助信号（高能=掌声/笑声/尖叫，仅供交叉验证）\n"
            for x in sig["excite"][:40]:
                timeline_text += f"- {x['start']:.1f}-{x['end']:.1f}s level={x['level']}\n"

    prompt = read_prompt()
    prompt = prompt.replace("{{TYPE}}", TYPE_NAMES.get(args.type, args.type))
    prompt = prompt.replace("{{TYPE_RULES}}", TYPE_RULES[args.type])
    prompt = prompt.replace("{{TARGET_DUR}}", str(args.target_dur))
    prompt = prompt.replace("{{TIMELINE}}", timeline_text)

    eprint(f"[analyze] 调用 {args.llm_model} 分析（类型: {args.type}）...")
    t0 = time.time()
    raw = call_llm(args.llm_base, args.llm_key, args.llm_model,
                   [{"role": "system", "content": prompt[:12000]},
                    {"role": "user", "content": timeline_text[:80000]}])
    eprint(f"[analyze] LLM 返回 {time.time()-t0:.1f}s")
    data = extract_json(raw)
    clips = data.get("clips") or data.get("highlights") or []
    if not clips:
        raise SystemExit(f"LLM 没返回任何片段:\n{raw[:600]}")

    # 时间对齐 + 排序 + 截断
    for c in clips:
        c["start"], c["end"] = align(float(c.get("start", 0)), float(c.get("end", 0)), segs)
        c["score"] = round(min(1.0, max(0.0, float(c.get("score", 0.5)))), 3)
        c.setdefault("type", "高能")
        c.setdefault("quote", "")
        c.setdefault("reason", "")
        c.setdefault("title", "")
        c.setdefault("speakers", [])
    clips.sort(key=lambda c: c["score"], reverse=True)
    clips = clips[: args.max_clips]

    base = os.path.splitext(os.path.basename(args.timeline))[0].replace("_timeline", "")
    # 默认工作目录 = 素材根目录/clip_work（timeline 位于 <root>/clip_work/timeline/ 时取上两级）
    tl_dir = os.path.dirname(os.path.abspath(args.timeline))
    if os.path.basename(tl_dir) == "timeline":
        root = os.path.dirname(os.path.dirname(tl_dir))
    else:
        root = os.path.dirname(tl_dir)
    workdir = args.outdir if os.path.isabs(args.outdir) else os.path.join(root, args.outdir)
    hdir = os.path.join(workdir, "highlights")
    os.makedirs(hdir, exist_ok=True)

    hl_path = os.path.join(hdir, f"{base}_highlights.json")
    with open(hl_path, "w", encoding="utf-8") as f:
        json.dump({"type": args.type, "clips": clips}, f, ensure_ascii=False, indent=1)

    # 从 timeline.md 头部解析源视频路径
    src_match = re.search(r"源: `([^`]+)`", timeline_text)
    source = src_match.group(1) if src_match else ""
    edl = {
        "version": 1,
        "sources": {"__MAIN__": source} if source else {},
        "ranges": [
            {"source": "__MAIN__", "start": c["start"], "end": c["end"],
             "beat": c["type"], "quote": c.get("quote", ""), "reason": c.get("reason", "")}
            for c in clips
        ],
        "highlights": clips,
    }
    edl_path = os.path.join(hdir, f"{base}_edl.json")
    with open(edl_path, "w", encoding="utf-8") as f:
        json.dump(edl, f, ensure_ascii=False, indent=1)

    eprint(f"[analyze] 高光 {len(clips)} 条，最高分 {clips[0]['score']}：{clips[0].get('reason','')}")
    eprint(f"[analyze] 已写入 {hl_path}")
    print(hl_path)
    print(edl_path)


if __name__ == "__main__":
    main()
