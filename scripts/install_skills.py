#!/usr/bin/env python3
"""Safely install this repository's Skills into a workspace/.user_skills directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILL_NAMES = ("podcast-weekly-collector", "podcast-transcript-cleaner")
IGNORED_NAMES = {"__pycache__", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def validate_target(path: Path) -> Path:
    target = path.expanduser().resolve()
    if target.name != ".user_skills" or target.parent.name != "workspace":
        raise ValueError("--target 必须是路径以 workspace/.user_skills 结尾的目录")
    if not target.is_dir():
        raise FileNotFoundError(f"目标目录不存在：{target}")
    return target


def validate_sources(repo_root: Path) -> dict[str, Path]:
    skill_root = repo_root / "skills"
    sources = {}
    for name in SKILL_NAMES:
        source = skill_root / name
        if not (source / "SKILL.md").is_file():
            raise FileNotFoundError(f"Skill 不完整，缺少：{source / 'SKILL.md'}")
        sources[name] = source
    return sources


def ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in IGNORED_NAMES or Path(name).suffix in IGNORED_SUFFIXES
    }


def copy_skill(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=ignore)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="安装 podcast-weekly-collector 与 podcast-transcript-cleaner。"
    )
    parser.add_argument("--target", required=True, help="实际的 workspace/.user_skills 目录")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不写文件")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="备份后升级已存在的同名 Skill；未指定时遇到同名目录即停止",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    try:
        target = validate_target(Path(args.target))
        sources = validate_sources(repo_root)
    except (ValueError, FileNotFoundError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 2

    existing = [name for name in SKILL_NAMES if (target / name).exists()]
    plan = {
        "ok": True,
        "dry_run": args.dry_run,
        "target": str(target),
        "skills": list(SKILL_NAMES),
        "existing": existing,
        "overwrite": args.overwrite,
    }
    if existing and not args.overwrite:
        plan.update({
            "ok": False,
            "error": "目标中已存在同名 Skill；请先检查差异，确认升级后使用 --overwrite。",
        })
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 3

    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    backup_root = None
    if existing:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = target / ".skill-backups" / timestamp
        backup_root.mkdir(parents=True, exist_ok=False)
        for name in existing:
            shutil.copytree(target / name, backup_root / name, ignore=ignore)

    staging_root = target / ".podcast-skills-installing"
    if staging_root.exists():
        raise RuntimeError(f"发现未清理的安装暂存目录：{staging_root}")
    staging_root.mkdir()
    try:
        for name, source in sources.items():
            copy_skill(source, staging_root / name)
        for name in SKILL_NAMES:
            destination = target / name
            if destination.exists():
                shutil.rmtree(destination)
            (staging_root / name).replace(destination)
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)

    plan["backup"] = str(backup_root) if backup_root else None
    plan["installed"] = [str(target / name) for name in SKILL_NAMES]
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
