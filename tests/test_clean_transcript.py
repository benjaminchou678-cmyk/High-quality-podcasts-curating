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


def write_episode(root, name, metadata, segments, topic_digest=None, translations=None):
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
    if translations is not None:
        (transcript / "translations.zh.json").write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")
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

        bilingual = write_episode(root, "bilingual", {"transcript_language": "en", "speaker_mode": "multi"}, [
            {"start_time": 0, "end_time": 5, "speaker": "host", "text": "Welcome to the show.", "confidence": 0.99},
            {"start_time": 6, "end_time": 12, "speaker": "guest", "text": "Artificial intelligence changes scientific discovery.", "confidence": 0.99},
        ], {
            "version": "1.0", "source": "transcript", "items": [{
                "topic": "人工智能如何改变科学发现", "summary": "嘉宾讨论人工智能对科研流程的影响。", "start_time": 0, "end_time": 12,
                "points": [{"text": "节目以主题介绍开场。", "start_time": 0, "end_time": 5}],
            }],
        }, {"items": [
            {"start_time": 0, "end_time": 5, "translation_zh": "欢迎来到本期节目。"},
            {"start_time": 6, "end_time": 12, "translation_zh": "人工智能正在改变科学发现。"},
        ]})
        module.clean_episode(bilingual)
        bilingual_blocks = load(bilingual / "transcript" / "dialogue.readable.json")
        bilingual_report = load(bilingual / "transcript" / "quality-report.json")
        bilingual_md = (bilingual / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert bilingual_report["metrics"]["translation_required"] is True
        assert bilingual_report["metrics"]["translation_coverage_ratio"] == 1.0
        assert all(block.get("translation_zh") for block in bilingual_blocks)
        assert bilingual_md.index("欢迎来到本期节目") < bilingual_md.index("Welcome to the show")
        assert "> **英文原文**" in bilingual_md
        assert "人工智能如何改变科学发现" in bilingual_md

        incomplete = write_episode(root, "incomplete", {"transcript_language": "en"}, [
            {"start_time": 0, "end_time": 5, "speaker": "one", "text": "First English sentence.", "confidence": 0.99},
            {"start_time": 6, "end_time": 11, "speaker": "one", "text": "Second English sentence.", "confidence": 0.99},
        ], translations={"items": [
            {"start_time": 0, "end_time": 5, "translation_zh": "第一句英文的中文翻译。"},
        ]})
        module.clean_episode(incomplete)
        incomplete_report = load(incomplete / "transcript" / "quality-report.json")
        incomplete_md = (incomplete / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert incomplete_report["metrics"]["translation_coverage_ratio"] == 0.5
        assert incomplete_report["metrics"]["translation_missing_count"] == 1
        assert "translation_incomplete" in {risk["code"] for risk in incomplete_report["risks"]}
        assert "中文译文待补" in incomplete_md

        chinese = write_episode(root, "chinese", {}, [
            {"start_time": 0, "end_time": 5, "speaker": "one", "text": "这是一段中文访谈。", "confidence": 0.99},
        ])
        module.clean_episode(chinese)
        chinese_report = load(chinese / "transcript" / "quality-report.json")
        chinese_md = (chinese / "transcript" / "transcript.readable.md").read_text(encoding="utf-8")
        assert chinese_report["metrics"]["translation_required"] is False
        assert "英文原文" not in chinese_md

    print("speaker mode, topic digest, and bilingual transcript tests passed")


if __name__ == "__main__":
    main()
