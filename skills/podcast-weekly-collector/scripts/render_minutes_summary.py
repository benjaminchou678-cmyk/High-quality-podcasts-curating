#!/usr/bin/env python3
"""Render a Chinese, two-level Minutes summary from one authoritative digest."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


def stamp(seconds: float) -> str:
    value = int(seconds)
    return f"{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}"


def boundary(item: dict, key: str) -> float:
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be an explicit finite nonnegative number")
    return float(value)


def plain_zh(value, required=True) -> str:
    if not required and value == "":
        return ""
    if not isinstance(value, str) or not value.strip() or not re.search(r"[\u4e00-\u9fff]", value):
        raise ValueError("bullet text must be nonempty Chinese prose (English proper nouns allowed)")
    if any(c in value for c in ("\n", "\r", "`", "[", "]", "<", ">", "*")):
        raise ValueError("bullet fields must be plain text, not embedded Markdown or HTML")
    return value.strip()


def render_summary(topic_digest: dict) -> str:
    if not isinstance(topic_digest, dict) or topic_digest.get("source", "transcript") != "transcript":
        raise ValueError("digest must be based on transcript")
    items = topic_digest.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 8:
        raise ValueError("digest must contain 1–8 topics (normally 3–8; do not pad short episodes)")
    lines = ["# 议题提要", ""]
    previous_start = -1
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("topic must be an object")
        topic = plain_zh(item.get("topic"))
        summary = plain_zh(item.get("summary", ""), required=False)
        start, end = boundary(item, "start_time"), boundary(item, "end_time")
        if end < start or start < previous_start:
            raise ValueError("invalid or unordered topic time range")
        previous_start = start
        suffix = f"：{summary}" if summary else ""
        lines.append(f"- **{topic}**（{stamp(start)}–{stamp(end)}）{suffix}")
        points = item.get("points")
        if not isinstance(points, list) or not 1 <= len(points) <= 6:
            raise ValueError("each topic requires 1–6 supporting points")
        for point in points:
            if not isinstance(point, dict) or "points" in point:
                raise ValueError("digest must have at most two levels")
            text = plain_zh(point.get("text"))
            pstart, pend = boundary(point, "start_time"), boundary(point, "end_time")
            if pstart < start or pend < pstart or pend > end:
                raise ValueError("point range is outside topic range")
            lines.append(f"  - {text}（{stamp(pstart)}–{stamp(pend)}）")
        lines.append("")
    lines.extend(["## 说明", "", "- 本提要基于完整妙记逐字稿生成；逐字稿正文保持节目原语言。",
                  "- 说话人编号来自妙记分区，不代表已核验的真实身份。",
                  "- 妙记为机器转写，专有名词和数字建议结合原音频复核。", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="将 topic-digest.json 渲染为妙记总结兼容 Markdown。")
    parser.add_argument("topic_digest")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source, output = Path(args.topic_digest), Path(args.output)
    if source.resolve() == output.resolve():
        raise ValueError("output cannot overwrite topic-digest input")
    digest = json.loads(source.read_text(encoding="utf-8"))
    rendered = render_summary(digest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(rendered)
    print(json.dumps({"output": str(output), "topic_count": len(digest["items"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
