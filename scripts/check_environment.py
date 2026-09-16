#!/usr/bin/env python3
"""Read-only environment checks for the podcast Skills."""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import sys
from pathlib import Path

SKILLS = ("podcast-weekly-collector", "podcast-transcript-cleaner")
ASR_HINTS = (
    "mediakit-cli",
    "whisper",
    "whisper-cli",
    "faster-whisper",
    "ffmpeg",
)
LARK_HINTS = ("lark-cli",)


def command_status(name: str) -> dict:
    path = shutil.which(name)
    return {"name": name, "available": bool(path), "path": path}


def main() -> int:
    parser = argparse.ArgumentParser(description="检查播客 Skill 的本地运行环境。")
    parser.add_argument(
        "--skills-root",
        help="可选：已安装的 workspace/.user_skills 路径；省略时检查仓库 skills/。",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    skills_root = Path(args.skills_root).expanduser().resolve() if args.skills_root else repo_root / "skills"
    skill_checks = []
    for name in SKILLS:
        root = skills_root / name
        skill_md = root / "SKILL.md"
        skill_checks.append({
            "name": name,
            "root": str(root),
            "directory_exists": root.is_dir(),
            "skill_md_exists": skill_md.is_file(),
            "scripts_directory_exists": (root / "scripts").is_dir(),
        })

    sources_path = skills_root / "podcast-weekly-collector" / "assets" / "default-sources.json"
    source_check = {"path": str(sources_path), "exists": sources_path.is_file(), "count": None, "valid": False}
    if sources_path.is_file():
        try:
            sources = json.loads(sources_path.read_text(encoding="utf-8"))
            source_check["count"] = len(sources) if isinstance(sources, list) else None
            source_check["valid"] = (
                isinstance(sources, list)
                and all(isinstance(item, dict) and item.get("id") and item.get("name") and item.get("feed_url") for item in sources)
            )
        except (OSError, json.JSONDecodeError) as error:
            source_check["error"] = str(error)

    result = {
        "python": {
            "version": platform.python_version(),
            "supported": sys.version_info >= (3, 10),
        },
        "skills_root": str(skills_root),
        "skills": skill_checks,
        "default_sources": source_check,
        "optional_commands": {
            "git": command_status("git"),
            "github_cli": command_status("gh"),
            "asr_hints": [command_status(name) for name in ASR_HINTS],
            "lark_hints": [command_status(name) for name in LARK_HINTS],
        },
        "notes": [
            "命令存在只说明本机可执行，不能证明账号、权限、额度或模型能力可用。",
            "ASR 完整能力需实测时间戳、置信度和 speaker diarization。",
            "飞书输出需运行环境提供文档工具并完成登录授权。",
        ],
    }
    required_ok = (
        result["python"]["supported"]
        and all(item["directory_exists"] and item["skill_md_exists"] for item in skill_checks)
        and source_check["valid"]
    )
    result["required_checks_passed"] = required_ok
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
