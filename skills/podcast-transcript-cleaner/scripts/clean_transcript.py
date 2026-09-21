#!/usr/bin/env python3
"""Deterministically create a readable podcast transcript and quality report."""

import argparse
import html
import json
import math
import re
from pathlib import Path

END_PUNCT = tuple("。！？…?!")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stamp(seconds):
    seconds = max(0, int(float(seconds or 0)))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def duration_seconds(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        parts = [float(part) for part in str(value).split(":")]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] if parts else None


def normalize_text(value):
    text = re.sub(r"[ \t\u3000]+", " ", str(value or "").strip())
    text = re.sub(r"\s+([，。！？；：、])", r"\1", text)
    text = re.sub(r"([，。！？；：、])\s+", r"\1", text)
    replacements = {",": "，", ";": "；", ":": "：", "?": "？", "!": "！"}
    for source, target in replacements.items():
        text = re.sub(rf"(?<=[\u4e00-\u9fff]){re.escape(source)}", target, text)
    return text


def canonical_segments(raw):
    segments = []
    for item in raw:
        start = float(item.get("start_time", 0) or 0)
        end = float(item.get("end_time", start) or start)
        speaker = item.get("speaker")
        record = {
            "start_time": start,
            "end_time": end,
            "speaker": str(speaker) if speaker not in (None, "") else "未确定",
            "text": normalize_text(item.get("text", item.get("subtitle_text", ""))),
        }
        if isinstance(item.get("confidence"), (int, float)):
            record["confidence"] = float(item["confidence"])
        segments.append(record)
    return segments


def resolve_speakers(segments, metadata):
    requested = str(metadata.get("speaker_mode", "auto") or "auto").lower()
    expected = metadata.get("expected_speaker_count")
    if metadata.get("single_speaker") is True or expected == 1:
        requested = "single"
    if requested not in {"single", "multi", "auto"}:
        raise ValueError("speaker_mode must be single, multi, or auto")

    raw_labels = []
    raw_counts = {}
    nonempty_count = 0
    raw_missing = 0
    for segment in segments:
        if not segment["text"]:
            continue
        nonempty_count += 1
        label = segment["speaker"]
        if label == "未确定":
            raw_missing += 1
            continue
        if label not in raw_counts:
            raw_labels.append(label)
            raw_counts[label] = 0
        raw_counts[label] += 1

    if requested == "single":
        resolved = "single"
    elif requested == "multi":
        resolved = "multi"
    elif len(raw_labels) == 1 and raw_missing == 0:
        resolved = "single"
    elif len(raw_labels) >= 2:
        resolved = "multi"
    else:
        resolved = "unknown"

    remap = {}
    if resolved == "single":
        remap = {label: "1" for label in raw_labels}
        for segment in segments:
            if segment["text"]:
                segment["speaker"] = "1"
    elif resolved == "multi":
        remap = {label: str(index) for index, label in enumerate(raw_labels, 1)}
        for segment in segments:
            if segment["speaker"] != "未确定":
                segment["speaker"] = remap[segment["speaker"]]
    elif raw_labels:
        remap = {label: str(index) for index, label in enumerate(raw_labels, 1)}
        for segment in segments:
            if segment["speaker"] != "未确定":
                segment["speaker"] = remap[segment["speaker"]]

    normalized_counts = {}
    for segment in segments:
        if not segment["text"] or segment["speaker"] == "未确定":
            continue
        label = segment["speaker"]
        normalized_counts[label] = normalized_counts.get(label, 0) + 1

    rare_raw_labels = []
    if resolved == "multi" and nonempty_count >= 20:
        rare_limit = max(2, math.ceil(nonempty_count * 0.002))
        rare_raw_labels = [label for label, count in raw_counts.items() if count <= rare_limit]

    return segments, {
        "speaker_mode_requested": requested,
        "speaker_mode_resolved": resolved,
        "expected_speaker_count": expected if isinstance(expected, int) else None,
        "raw_speaker_count": len(raw_labels),
        "normalized_speaker_count": len(normalized_counts),
        "raw_missing_speaker_ratio": raw_missing / nonempty_count if nonempty_count else 1.0,
        "speaker_segment_counts": normalized_counts,
        "speaker_remap": remap,
        "rare_raw_speaker_labels": rare_raw_labels,
    }


def exact_deduplicate(segments):
    output, removed = [], []
    for segment in segments:
        if (
            output and segment["text"] and segment["text"] == output[-1]["text"]
            and segment["start_time"] - output[-1]["end_time"] <= 0.5
        ):
            removed.append(segment)
            output[-1]["end_time"] = max(output[-1]["end_time"], segment["end_time"])
            continue
        output.append(segment)
    return output, removed


def merge_segments(segments, max_gap=3.0, max_chars=420):
    blocks = []
    for segment in segments:
        if not segment["text"]:
            continue
        long_gap = bool(blocks and segment["start_time"] - blocks[-1]["end_time"] > 10)
        can_merge = (
            blocks and not long_gap and blocks[-1]["speaker"] == segment["speaker"]
            and segment["start_time"] - blocks[-1]["end_time"] <= max_gap
            and len(blocks[-1]["text"]) + len(segment["text"]) <= max_chars
        )
        if can_merge:
            previous = blocks[-1]
            joiner = "" if previous["text"].endswith(("，", "。", "！", "？", ",", ".", "!", "?", "…")) else "，"
            previous["text"] += joiner + segment["text"]
            previous["end_time"] = max(previous["end_time"], segment["end_time"])
            if "confidence" in segment:
                previous["confidences"].append(segment["confidence"])
        else:
            blocks.append({
                "start_time": segment["start_time"], "end_time": segment["end_time"],
                "speaker": segment["speaker"], "text": segment["text"],
                "confidences": [segment["confidence"]] if "confidence" in segment else [],
            })
    for block in blocks:
        if block["text"] and not block["text"].endswith(END_PUNCT):
            block["text"] += "。"
        confidences = block.pop("confidences")
        block["mean_confidence"] = sum(confidences) / len(confidences) if confidences else None
    return blocks


def extract_chapters(shownotes, duration):
    normalized = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h[1-6]>", "\n", shownotes)
    normalized = html.unescape(re.sub(r"<[^>]+>", "", normalized))
    chapters, seen = [], set()
    for line in normalized.splitlines():
        matches = list(re.finditer(r"(?<!\d)(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)(?!\d)", line))
        for index, match in enumerate(matches):
            seconds = int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
            end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            title = re.sub(r"^[\s—–\-|｜:：]+", "", line[match.end():end]).strip()
            if not title or seconds in seen or (duration is not None and seconds > duration):
                continue
            seen.add(seconds)
            chapters.append({"start_time": seconds, "title": title, "source": "shownotes"})
    chapters.sort(key=lambda item: item["start_time"])
    if chapters:
        return chapters, False
    upper = int(duration or 0)
    if upper <= 0:
        return [{"start_time": 0, "title": "自动分段 1", "source": "automatic"}], True
    return [
        {"start_time": seconds, "title": f"自动分段 {index}", "source": "automatic"}
        for index, seconds in enumerate(range(0, upper + 1, 900), 1)
    ], True


def quality(segments, expected_duration, actual_duration, automatic_chapters, upstream, speaker_info):
    nonempty = [segment for segment in segments if segment["text"]]
    confidences = [segment["confidence"] for segment in segments if isinstance(segment.get("confidence"), (int, float))]
    missing_speakers = sum(segment["speaker"] == "未确定" for segment in nonempty)
    order_errors = sum(segments[index]["start_time"] < segments[index - 1]["start_time"] for index in range(1, len(segments)))
    gaps = []
    for previous, current in zip(segments, segments[1:]):
        gap = current["start_time"] - previous["end_time"]
        if gap > 10:
            gaps.append({"start_time": previous["end_time"], "end_time": current["start_time"], "seconds": gap})
    coverage = actual_duration / expected_duration if actual_duration and expected_duration else None
    low = sum(value < 0.80 for value in confidences) / len(confidences) if confidences else None
    very_low = sum(value < 0.60 for value in confidences) / len(confidences) if confidences else None
    missing_ratio = missing_speakers / len(nonempty) if nonempty else 1.0
    risks, level_rank = [], 0

    def add(code, severity, detail):
        nonlocal level_rank
        risks.append({"code": code, "severity": severity, "detail": detail})
        level_rank = max(level_rank, {"notice": 1, "review_recommended": 2, "high_risk": 3}[severity])

    if automatic_chapters:
        add("automatic_chapters", "notice", "未发现可靠官方章节，使用每 15 分钟自动分段。")
    if coverage is None:
        add("coverage_unavailable", "review_recommended", "无法计算音频时长覆盖率。")
    elif coverage < 0.75:
        add("low_coverage", "high_risk", f"音频时长覆盖率为 {coverage:.1%}。")
    elif coverage < 0.90:
        add("low_coverage", "review_recommended", f"音频时长覆盖率为 {coverage:.1%}。")
    elif coverage < 0.95:
        add("low_coverage", "notice", f"音频时长覆盖率为 {coverage:.1%}。")
    if low is None:
        add("confidence_unavailable", "review_recommended", "ASR 未返回置信度。")
    elif low >= 0.30:
        add("low_confidence", "high_risk", f"低于 0.80 的片段占 {low:.1%}。")
    elif low >= 0.15:
        add("low_confidence", "review_recommended", f"低于 0.80 的片段占 {low:.1%}。")
    elif low >= 0.05:
        add("low_confidence", "notice", f"低于 0.80 的片段占 {low:.1%}。")
    if order_errors:
        add("timestamp_order_error", "high_risk", f"发现 {order_errors} 处时间戳逆序。")
    if missing_ratio:
        add("speaker_missing", "review_recommended", f"说话人未确定片段占 {missing_ratio:.1%}。")
    expected_speakers = speaker_info.get("expected_speaker_count")
    normalized_speakers = speaker_info.get("normalized_speaker_count", 0)
    if isinstance(expected_speakers, int) and expected_speakers > 0 and normalized_speakers != expected_speakers:
        add("speaker_count_mismatch", "review_recommended", f"预期 {expected_speakers} 位说话人，归一后识别为 {normalized_speakers} 位。")
    if speaker_info.get("speaker_mode_resolved") == "single" and speaker_info.get("raw_speaker_count", 0) > 1:
        add("single_mode_collapsed_clusters", "notice", f"单人模式将 ASR 的 {speaker_info['raw_speaker_count']} 个原始声纹聚类统一为说话人1。")
    rare_labels = speaker_info.get("rare_raw_speaker_labels", [])
    if rare_labels:
        add("rare_speaker_cluster", "notice", f"多人模式发现 {len(rare_labels)} 个稀有声纹聚类，未自动合并，建议抽查。")
    if len(gaps) > 3:
        add("long_gaps", "review_recommended", f"发现 {len(gaps)} 处超过 10 秒的长静默或缺口。")
    elif gaps:
        add("long_gaps", "notice", f"发现 {len(gaps)} 处超过 10 秒的长静默或缺口。")
    if not nonempty:
        add("empty_transcript", "high_risk", "没有可用正文。")
    if upstream.get("status") in {"transcript_mismatch", "manual_review_required"}:
        add("upstream_review", "review_recommended", f"上游状态为 {upstream.get('status')}。")
    return {
        "risk_level": ["normal", "notice", "review_recommended", "high_risk"][level_rank],
        "risks": risks,
        "metrics": {
            "segment_count": len(segments), "nonempty_segment_count": len(nonempty),
            "empty_text_count": len(segments) - len(nonempty), "duration_coverage_ratio": coverage,
            "low_confidence_ratio": low, "very_low_confidence_ratio": very_low,
            "missing_speaker_ratio": missing_ratio,
            "speaker_mode_requested": speaker_info.get("speaker_mode_requested"),
            "speaker_mode_resolved": speaker_info.get("speaker_mode_resolved"),
            "raw_speaker_count": speaker_info.get("raw_speaker_count"),
            "normalized_speaker_count": speaker_info.get("normalized_speaker_count"),
            "raw_missing_speaker_ratio": speaker_info.get("raw_missing_speaker_ratio"),
            "speaker_segment_counts": speaker_info.get("speaker_segment_counts"),
            "speaker_remap": speaker_info.get("speaker_remap"),
            "timestamp_order_errors": order_errors,
            "long_gap_count": len(gaps), "long_gaps": gaps,
        },
    }


def md_escape(value):
    text = str(value or "").replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "$", "~", "<"):
        text = text.replace(character, "\\" + character)
    return text


def validate_topic_digest(raw, duration):
    if raw in (None, {}):
        return {"version": "1.0", "source": "transcript", "items": []}
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ValueError("topic-digest.json must be an object with an items array")
    if str(raw.get("source", "transcript")) != "transcript":
        raise ValueError("topic-digest.json source must be transcript")
    items = []
    for index, item in enumerate(raw["items"], 1):
        if not isinstance(item, dict):
            raise ValueError(f"topic digest item {index} must be an object")
        topic = normalize_text(item.get("topic"))
        summary = normalize_text(item.get("summary"))
        if not topic:
            raise ValueError(f"topic digest item {index} has no topic")
        start = float(item.get("start_time", 0) or 0)
        end = float(item.get("end_time", start) or start)
        if start < 0 or end < start or (duration is not None and end > duration + 1):
            raise ValueError(f"topic digest item {index} has invalid time range")
        points = item.get("points", [])
        if not isinstance(points, list) or len(points) > 6:
            raise ValueError(f"topic digest item {index} points must be an array with at most 6 items")
        clean_points = []
        for point_index, point in enumerate(points, 1):
            if not isinstance(point, dict) or isinstance(point.get("points"), list):
                raise ValueError(f"topic digest item {index} point {point_index} must not contain nested points")
            text = normalize_text(point.get("text"))
            if not text:
                raise ValueError(f"topic digest item {index} point {point_index} has no text")
            point_start = float(point.get("start_time", start) or 0)
            point_end = float(point.get("end_time", point_start) or point_start)
            if point_start < 0 or point_end < point_start or point_start < start or point_end > end:
                raise ValueError(f"topic digest item {index} point {point_index} is outside its topic range")
            clean_points.append({"text": text, "start_time": point_start, "end_time": point_end})
        items.append({
            "topic": topic, "summary": summary, "start_time": start, "end_time": end,
            "points": clean_points,
        })
    return {"version": "1.0", "source": "transcript", "items": items}


def render_topic_digest(topic_digest):
    items = topic_digest.get("items", [])
    if not items:
        return []
    lines = ["## 议题提要", ""]
    for item in items:
        time_range = f"{stamp(item['start_time'])}–{stamp(item['end_time'])}"
        summary = f"：{md_escape(item['summary'])}" if item.get("summary") else ""
        lines.append(f"- **{md_escape(item['topic'])}**（{time_range}）{summary}")
        for point in item.get("points", []):
            point_range = f"{stamp(point['start_time'])}–{stamp(point['end_time'])}"
            lines.append(f"  - {md_escape(point['text'])}（{point_range}）")
    lines.append("")
    return lines


def build_markdown(metadata, chapters, blocks, report, topic_digest=None):
    date = str(metadata.get("published_at", ""))[:10]
    podcast = metadata.get("podcast_name", "未知节目")
    title = metadata.get("title", "未命名单集")
    risk_names = {"normal": "正常", "notice": "注意", "review_recommended": "建议人工复核", "high_risk": "高风险"}
    reasons = [risk["detail"] for risk in report["risks"]][:5]
    reason_text = "；".join(reasons) if reasons else "未发现显著机器风险。"
    source = metadata.get("transcript_source", metadata.get("transcript_status", "未知"))
    lines = [
        f"# {md_escape(date)}｜{md_escape(podcast)}｜{md_escape(title)}", "",
        "> ASR 机器转写，未经人工校对。",
        f"> 质量状态：{risk_names[report['risk_level']]}。{md_escape(reason_text)}",
        "> 说话人编号仅表示本文内不同声纹，不代表真实身份。", "",
        f"- **节目**：{md_escape(podcast)}", f"- **发布日期**：{md_escape(date)}",
        f"- **音频时长**：{md_escape(metadata.get('duration', ''))}",
        f"- **原节目页**：{metadata.get('episode_url', '')}", f"- **文字来源**：{md_escape(source)}", "",
    ]
    lines.extend(render_topic_digest(topic_digest or {"items": []}))
    lines.extend(["## 逐字稿", ""])
    chapter_index = 0
    for block in blocks:
        while chapter_index < len(chapters) and chapters[chapter_index]["start_time"] <= block["start_time"]:
            chapter = chapters[chapter_index]
            suffix = "（自动分段）" if chapter["source"] == "automatic" else ""
            lines.extend([f"## {stamp(chapter['start_time'])}｜{md_escape(chapter['title'])}{suffix}", ""])
            chapter_index += 1
        speaker = "未确定" if block["speaker"] == "未确定" else block["speaker"]
        confidence_mark = " · [低置信]" if isinstance(block.get("mean_confidence"), (int, float)) and block["mean_confidence"] < 0.80 else ""
        lines.extend([
            f"**{md_escape('说话人未确定' if block['speaker'] == '未确定' else '说话人' + block['speaker'])}** · {stamp(block['start_time'])}{confidence_mark}", "",
            md_escape(block["text"]), "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def clean_episode(episode_directory):
    episode_directory = Path(episode_directory)
    transcript_directory = episode_directory / "transcript"
    metadata_path = episode_directory / "metadata.json"
    segments_path = transcript_directory / "segments.raw.json"
    if not metadata_path.exists() or not segments_path.exists():
        raise FileNotFoundError("metadata.json and transcript/segments.raw.json are required")
    metadata = load_json(metadata_path)
    upstream_path = transcript_directory / "transcript.meta.json"
    upstream = load_json(upstream_path) if upstream_path.exists() else {}
    segments = canonical_segments(load_json(segments_path))
    segments, speaker_info = resolve_speakers(segments, metadata)
    segments, removed = exact_deduplicate(segments)
    blocks = merge_segments(segments)
    shownotes_path = episode_directory / "shownotes.raw.txt"
    shownotes = shownotes_path.read_text(encoding="utf-8") if shownotes_path.exists() else ""
    expected = duration_seconds(metadata.get("duration"))
    actual = duration_seconds(upstream.get("quality", {}).get("audio_duration_seconds"))
    actual = actual or max((segment["end_time"] for segment in segments), default=None)
    chapters, automatic = extract_chapters(shownotes, actual)
    topic_digest_path = transcript_directory / "topic-digest.json"
    topic_digest = validate_topic_digest(load_json(topic_digest_path) if topic_digest_path.exists() else None, actual)
    report = quality(segments, expected, actual, automatic, upstream, speaker_info)
    report["metrics"]["deduplicated_exact_count"] = len(removed)
    report["metrics"]["topic_digest_count"] = len(topic_digest["items"])
    report["episode_id"] = metadata.get("episode_id")
    report["cleaning_version"] = "1.3.0"
    render_metadata = dict(metadata)
    render_metadata["transcript_source"] = "ASR" if upstream.get("acquisition_method") == "asr" else upstream.get("acquisition_method", "未知")
    transcript_directory.mkdir(parents=True, exist_ok=True)
    (transcript_directory / "dialogue.readable.json").write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")
    (transcript_directory / "quality-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (transcript_directory / "transcript.readable.md").write_text(build_markdown(render_metadata, chapters, blocks, report, topic_digest), encoding="utf-8")
    upstream["cleaning"] = {
        "version": "1.3.0",
        "risk_level": report["risk_level"],
        "risk_codes": [risk["code"] for risk in report["risks"]],
        "speaker_mode_requested": speaker_info["speaker_mode_requested"],
        "speaker_mode_resolved": speaker_info["speaker_mode_resolved"],
        "normalized_speaker_count": speaker_info["normalized_speaker_count"],
        "topic_digest_file": "topic-digest.json" if topic_digest_path.exists() else None,
        "topic_digest_count": len(topic_digest["items"]),
        "readable_file": "transcript.readable.md",
        "quality_file": "quality-report.json",
    }
    upstream_path.write_text(json.dumps(upstream, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"episode_id": metadata.get("episode_id"), "risk_level": report["risk_level"], "blocks": len(blocks), "chapters": len(chapters), "topic_digest_count": len(topic_digest["items"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("episode_dir")
    arguments = parser.parse_args()
    print(json.dumps(clean_episode(arguments.episode_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
