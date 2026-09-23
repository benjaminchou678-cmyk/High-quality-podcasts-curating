#!/usr/bin/env python3
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "podcast-transcript-cleaner" / "scripts" / "clean_transcript.py"
spec = importlib.util.spec_from_file_location("clean_transcript", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_episode(root, name, metadata, segments, topic_digest=None):
    episode = root / name
    transcript = episode / "transcript"
    transcript.mkdir(parents=True)
    base = {
        "episode_id": name,
        "podcast_name": "测试播客",
        "title": name,
        "published_at": "2026-09-21",
        "duration": 60,
        "episode_url": "https://example.com/episode",
    }
    base.update(metadata)
    (episode / "metadata.json").write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    (transcript / "segments.raw.json").write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
    (transcript / "transcript.meta.json").write_text(json.dumps({"acquisition_method": "asr", "quality": {"audio_duration_seconds": 60}}, ensure_ascii=False), encoding="utf-8")
    if topic_digest is not None:
        (transcript / "topic-digest.json").write_text(json.dumps(topic_digest, ensure_ascii=False), encoding="utf-8")
    return episode


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        single = write_episode(root, "single", {"speaker_mode": "single"}, [
            {"start_time": 0, "end_time": 8, "speaker": "voice-a", "text": "第一段", "confidence": 0.99},
            {"start_time": 9, "end_time": 18, "speaker": "voice-b", "text": "第二段", "confidence": 0.99},
        ])
        module.clean_episode(single)
        single_blocks = load(single / "transcript" / "dialogue.readable.json")
        single_report = load(single / "transcript" / "quality-report.json")
        single_md = (single / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert {block["speaker"] for block in single_blocks} == {"1"}
        assert "说话人2" not in single_md and "说话人1" in single_md
        assert single_report["metrics"]["raw_speaker_count"] == 2
        assert single_report["metrics"]["normalized_speaker_count"] == 1
        assert "single_mode_collapsed_clusters" in {risk["code"] for risk in single_report["risks"]}

        multi = write_episode(root, "multi", {"speaker_mode": "multi", "expected_speaker_count": 4}, [
            {"start_time": 0, "end_time": 5, "speaker": "uuid-c", "text": "甲", "confidence": 0.99},
            {"start_time": 6, "end_time": 11, "speaker": "host", "text": "乙", "confidence": 0.99},
            {"start_time": 12, "end_time": 17, "speaker": "guest-z", "text": "丙", "confidence": 0.99},
            {"start_time": 18, "end_time": 23, "speaker": "fourth", "text": "丁", "confidence": 0.99},
            {"start_time": 24, "end_time": 30, "speaker": "host", "text": "乙再次发言", "confidence": 0.99},
        ], {
            "version": "1.0", "source": "transcript", "items": [{
                "topic": "四人讨论", "summary": "四位说话人依次发言。", "start_time": 0, "end_time": 30,
                "points": [{"text": "第二位说话人再次发言。", "start_time": 24, "end_time": 30}],
            }],
        })
        module.clean_episode(multi)
        multi_blocks = load(multi / "transcript" / "dialogue.readable.json")
        multi_report = load(multi / "transcript" / "quality-report.json")
        multi_md = (multi / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert [block["speaker"] for block in multi_blocks] == ["1", "2", "3", "4", "2"]
        assert multi_report["metrics"]["normalized_speaker_count"] == 4
        assert multi_report["metrics"]["speaker_remap"] == {"uuid-c": "1", "host": "2", "guest-z": "3", "fourth": "4"}
        assert "## 议题提要" in multi_md and "说话人4" in multi_md

        english = write_episode(root, "english", {"speaker_mode": "single"}, [
            {"start_time": 0, "end_time": 10, "speaker": "voice-a", "text": "Original English sentence.", "confidence": 0.99},
        ])
        (english / "transcript" / "transcript.meta.json").write_text(json.dumps({
            "acquisition_method": "feishu_minutes",
            "source_url": "https://example.feishu.cn/minutes/obcndemo",
            "quality": {"audio_duration_seconds": 60},
        }, ensure_ascii=False), encoding="utf-8")
        module.clean_episode(english)
        english_md = (english / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert "Original English sentence." in english_md
        assert "Original English sentence.。" not in english_md
        assert "飞书妙记机器转写" in english_md
        assert "https://example.feishu.cn/minutes/obcndemo" not in english_md
        english_meta = load(english / "transcript" / "transcript.meta.json")
        assert english_meta["cleaning"]["minute_link_included"] is False

        english_private = write_episode(root, "english-private", {"speaker_mode": "single", "include_private_links": True}, [
            {"start_time": 0, "end_time": 10, "speaker": "voice-a", "text": "Original English sentence.", "confidence": 0.99},
        ])
        (english_private / "transcript" / "transcript.meta.json").write_text(json.dumps({
            "acquisition_method": "feishu_minutes",
            "source_url": "https://example.feishu.cn/minutes/obcndemo",
            "quality": {"audio_duration_seconds": 60},
        }, ensure_ascii=False), encoding="utf-8")
        module.clean_episode(english_private)
        private_md = (english_private / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert "https://example.feishu.cn/minutes/obcndemo" in private_md
        private_meta = load(english_private / "transcript" / "transcript.meta.json")
        assert private_meta["cleaning"]["minute_link_included"] is True

        unknown = write_episode(root, "unknown", {}, [
            {"start_time": 0, "end_time": 5, "speaker": "only-known", "text": "已有标签", "confidence": 0.99},
            {"start_time": 6, "end_time": 11, "text": "没有标签", "confidence": 0.99},
        ])
        module.clean_episode(unknown)
        unknown_blocks = load(unknown / "transcript" / "dialogue.readable.json")
        unknown_report = load(unknown / "transcript" / "quality-report.json")
        unknown_md = (unknown / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert unknown_report["metrics"]["speaker_mode_resolved"] == "unknown"
        assert [block["speaker"] for block in unknown_blocks] == ["1", "未确定"]
        assert "speaker_missing" in {risk["code"] for risk in unknown_report["risks"]}
        assert "说话人1" in unknown_md and "说话人未确定" in unknown_md
        assert "only-known" not in unknown_md

    print("speaker mode and topic digest tests passed")


if __name__ == "__main__":
    main()
