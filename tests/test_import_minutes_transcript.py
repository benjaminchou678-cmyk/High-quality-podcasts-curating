#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT_SCRIPT = ROOT / "skills" / "podcast-weekly-collector" / "scripts" / "import_minutes_transcript.py"
SUMMARY_SCRIPT = ROOT / "skills" / "podcast-weekly-collector" / "scripts" / "render_minutes_summary.py"
CLEAN_SCRIPT = ROOT / "skills" / "podcast-transcript-cleaner" / "scripts" / "clean_transcript.py"


def loaded(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


importer = loaded("minutes_importer", IMPORT_SCRIPT)
summary = loaded("minutes_summary", SUMMARY_SCRIPT)
cleaner = loaded("clean_transcript", CLEAN_SCRIPT)

SAMPLE = """2026-09-22 16:22:28 CST|0h 0min 12s

Keywords:
产品、投资

Speaker 1 00:00:01.500
第一行。
第二行保留。

Speaker guest-A 00:00:05.000
Second segment.

说话人 1 00:00:09.250
最后一段。
"""

DIGEST = {"source": "transcript", "items": [{
    "topic": "硬科技投资", "summary": "讨论产业链方法。", "start_time": 1.5, "end_time": 12,
    "points": [{"text": "保留时间证据。", "start_time": 5, "end_time": 9.25}],
}]}


def raises(error_type, function, *args):
    try:
        function(*args)
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


def main():
    records, duration = importer.parse_minutes_transcript(SAMPLE)
    assert duration == 12
    assert [record.get("speaker") for record in records] == ["1", "guest-A", "1"]
    assert [record["end_time_basis"] for record in records] == ["next_start", "next_start", "media_duration"]
    assert all(record["end_time_estimated"] for record in records)
    assert records[0]["text"] == "第一行。\n第二行保留。"
    raises(ValueError, importer.parse_minutes_transcript, "Speaker 1 00:99:00\ntext")
    raises(ValueError, importer.parse_minutes_transcript, "Speaker 1 00:00:01\n")
    raises(ValueError, importer.parse_minutes_transcript, "Speaker 1 00:00:05\na\nSpeaker 2 00:00:04\nb")

    rendered = summary.render_summary(DIGEST)
    assert "硬科技投资" in rendered and "00:00:01–00:00:12" in rendered
    bad = json.loads(json.dumps(DIGEST)); del bad["items"][0]["points"][0]["start_time"]
    raises(ValueError, summary.render_summary, bad)
    bad = json.loads(json.dumps(DIGEST)); bad["items"][0]["topic"] = "Only English"
    raises(ValueError, summary.render_summary, bad)

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        episode = root / "episode"; episode.mkdir()
        (episode / "metadata.json").write_text(json.dumps({
            "episode_id": "demo", "podcast_name": "测试播客", "title": "测试单集",
            "published_at": "2026-09-22", "duration": 12,
            "episode_url": "https://example.com/episode", "speaker_mode": "multi",
        }), encoding="utf-8")
        source = root / "transcript.txt"; source.write_bytes(SAMPLE.encode("utf-8"))
        result = importer.import_transcript(source, episode,
            "https://example.feishu.cn/minutes/obcndemo",
            "https://example.feishu.cn/file/boxdemo")
        transcript = episode / "transcript"
        segments = json.loads((transcript / "segments.raw.json").read_text(encoding="utf-8"))
        meta = json.loads((transcript / "transcript.meta.json").read_text(encoding="utf-8"))
        assert result["end_times_estimated"] and meta["quality"]["audio_duration_seconds"] is None
        assert (transcript / "minutes.transcript.raw.txt").read_bytes() == source.read_bytes()
        raises(FileExistsError, importer.import_transcript, source, episode,
               "https://example.feishu.cn/minutes/obcndemo", None)
        raises(ValueError, importer.import_transcript, source, root / "other",
               "https://example.feishu.cn/minutes/obcndemo?ticket=secret", None)

        (transcript / "topic-digest.json").write_text(json.dumps(DIGEST, ensure_ascii=False), encoding="utf-8")
        cleaner.clean_episode(episode)
        report = json.loads((transcript / "quality-report.json").read_text(encoding="utf-8"))
        markdown = (transcript / "transcript.readable.md").read_text(encoding="utf-8")
        assert report["metrics"]["duration_coverage_ratio"] is None
        assert report["metrics"]["long_gap_count"] is None
        assert "end_times_estimated" in {r["code"] for r in report["risks"]}
        assert "第一行。\n第二行保留。" in markdown
        assert "https://example.feishu.cn/minutes/obcndemo" not in markdown

        digest_file, output = transcript / "topic-digest.json", transcript / "minutes-summary.md"
        subprocess.run([sys.executable, str(SUMMARY_SCRIPT), str(digest_file), "--output", str(output)], check=True)
        assert output.is_file()
        completed = subprocess.run([sys.executable, str(SUMMARY_SCRIPT), str(digest_file), "--output", str(output)], capture_output=True)
        assert completed.returncode != 0

    print("minutes import, summary and cleaning tests passed")


if __name__ == "__main__":
    main()
