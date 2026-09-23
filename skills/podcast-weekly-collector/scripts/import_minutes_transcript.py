#!/usr/bin/env python3
"""Import Minutes TXT without overwriting evidence or inventing precise end times."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit

SPEAKER_LINE = re.compile(
    r"^(?:Speaker\s+|说话人\s*)(.+?)\s+(\d{1,3}:\d{2}:\d{2}(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
DURATION_PART = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)min)?\s*(?:(\d+(?:\.\d+)?)s)?", re.I)


def timestamp_seconds(value: str) -> float:
    if not re.fullmatch(r"\d{1,3}:[0-5]\d:[0-5]\d(?:\.\d+)?", value):
        raise ValueError(f"invalid timestamp: {value!r}")
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def header_duration(text: str) -> float | None:
    lines = text.lstrip("\ufeff").splitlines()
    first_line = lines[0].strip() if lines else ""
    if "|" not in first_line:
        return None
    value = first_line.rsplit("|", 1)[-1].strip()
    match = DURATION_PART.fullmatch(value)
    if not match or not any(match.groups()):
        return None
    duration = int(match.group(1) or 0) * 3600 + int(match.group(2) or 0) * 60 + float(match.group(3) or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("invalid Minutes media duration")
    return duration


def parse_minutes_transcript(text: str) -> tuple[list[dict], float | None]:
    duration = header_duration(text)
    records: list[dict] = []
    current: dict | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current, body_lines
        if current is not None:
            body = "\n".join(body_lines).strip()
            if not body:
                raise ValueError("empty speaker block; preserve source and review instead of dropping it")
            current["text"] = body
            records.append(current)
        current, body_lines = None, []

    for raw_line in text.lstrip("\ufeff").splitlines():
        line = raw_line.rstrip()
        match = SPEAKER_LINE.fullmatch(line.strip())
        if match:
            flush()
            label = match.group(1).strip()
            current = {"start_time": timestamp_seconds(match.group(2))}
            if label.lower() not in {"unknown", "unidentified", "未确定", "未知"}:
                current["speaker"] = label
        elif re.match(r"^(?:Speaker\s+|说话人).*\d+:", line, re.I):
            raise ValueError("unrecognized speaker timestamp header")
        elif current is not None:
            body_lines.append(line)
    flush()
    if not records:
        raise ValueError("no Speaker + timestamp blocks found")
    starts = [record["start_time"] for record in records]
    if any(b < a for a, b in zip(starts, starts[1:])):
        raise ValueError("Minutes transcript timestamps are not monotonic")
    if duration is not None and starts[-1] > duration:
        raise ValueError("Minutes transcript starts after the declared duration")
    for index, record in enumerate(records):
        if index + 1 < len(records):
            end, basis = starts[index + 1], "next_start"
        elif duration is not None:
            end, basis = duration, "media_duration"
        else:
            end, basis = record["start_time"], "unknown"
        # Compatibility boundary only; these are NOT observed speech end times.
        record.update(end_time=end, end_time_estimated=True, end_time_basis=basis)
    return records, duration


def validate_url(value: str, resource: str) -> str:
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("URL must be a single HTTP/HTTPS URL")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(rf"/{resource}/[A-Za-z0-9_-]+", parsed.path)):
        raise ValueError(f"expected canonical /{resource}/ URL without credentials or tickets")
    return value


def import_transcript(transcript_file: Path, episode_dir: Path, minute_url: str,
                      audio_file_url: str | None, overwrite: bool = False) -> dict:
    if overwrite:
        raise ValueError("evidence is immutable; use a new run directory, not --overwrite")
    validate_url(minute_url, "minutes")
    if audio_file_url:
        validate_url(audio_file_url, "file")
    metadata_path = episode_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or not metadata.get("episode_id"):
        raise ValueError("metadata.json must have an episode_id")
    raw_bytes = transcript_file.read_bytes()
    raw_text = raw_bytes.decode("utf-8-sig")
    segments, duration = parse_minutes_transcript(raw_text)
    transcript_dir = episode_dir / "transcript"
    filenames = ("minutes.transcript.raw.txt", "segments.raw.json", "transcript.meta.json")
    paths = [transcript_dir / name for name in filenames]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise FileExistsError("transcript evidence exists; reuse it or use a new run directory")
    meta = {
        "episode_id": metadata["episode_id"],
        "acquisition_method": "feishu_minutes",
        "status": "minutes_transcript_generated",
        "source_url": minute_url,
        "audio_file_url": audio_file_url,
        "raw_transcript_file": filenames[0],
        "raw_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "quality": {
            "media_duration_seconds": duration,
            "audio_duration_seconds": None,
            "end_times_estimated": True,
            "speaker_labels_available": all(item.get("speaker") for item in segments),
            "confidence_available": False,
        },
    }
    payloads = [raw_bytes, (json.dumps(segments, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")]
    transcript_dir.mkdir(parents=True, exist_ok=True)
    for path, payload in zip(paths, payloads):
        with path.open("xb") as stream:
            stream.write(payload)
    return {"segments": len(segments), "speaker_count": len({s["speaker"] for s in segments if s.get("speaker")}),
            "duration_seconds": duration, "end_times_estimated": True,
            "segments_file": str(paths[1]), "meta_file": str(paths[2])}


def main() -> None:
    parser = argparse.ArgumentParser(description="导入妙记逐字稿；拒绝覆盖原始证据，结束时间仅为推算边界。")
    parser.add_argument("transcript_file")
    parser.add_argument("episode_dir")
    parser.add_argument("--minute-url", required=True)
    parser.add_argument("--audio-file-url")
    args = parser.parse_args()
    print(json.dumps(import_transcript(Path(args.transcript_file), Path(args.episode_dir),
          args.minute_url, args.audio_file_url), ensure_ascii=False))


if __name__ == "__main__":
    main()
