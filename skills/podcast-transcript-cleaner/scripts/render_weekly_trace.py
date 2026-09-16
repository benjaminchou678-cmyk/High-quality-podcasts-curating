#!/usr/bin/env python3
"""Render a compact weekly trace table from a public manifest."""

import argparse
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def compact_date(value):
    parsed = parse_datetime(value)
    return parsed.strftime("%Y%m%d") if parsed else str(value or "")[:10].replace("-", "")


def groups_from(manifest):
    deduplicated = {}
    for episode in manifest.get("episodes", []):
        episode_id = episode.get("episode_id")
        if episode_id and episode_id not in deduplicated:
            deduplicated[episode_id] = episode
    source_order = [source.get("name") for source in manifest.get("sources", []) if source.get("name")]
    groups = OrderedDict((name, []) for name in source_order)
    for episode in deduplicated.values():
        name = episode.get("podcast_name", "未知节目")
        groups.setdefault(name, []).append(episode)
    for name in list(groups):
        groups[name].sort(
            key=lambda item: (parse_datetime(item.get("published_at")) or datetime.min, item.get("episode_id", "")),
            reverse=True,
        )
        if not groups[name]:
            del groups[name]
    return groups


def escape_cell(value):
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("[", "\\[").replace("]", "\\]")


def render_markdown(manifest):
    lines = ["## 本周踪迹", "", "|  |  |", "|---|---|"]
    for name, episodes in groups_from(manifest).items():
        items = []
        for episode in episodes:
            label = f"{episode.get('title', '未命名单集')}_{compact_date(episode.get('published_at'))}"
            target = episode.get("transcript_markdown") or episode.get("transcript_url")
            title = f"[{label}]({target})" if target else f"{label} [未同步]"
            synced_at = episode.get("synced_at") or manifest.get("generated_at") or "同步时间未知"
            parsed = parse_datetime(synced_at)
            display_time = parsed.strftime("%Y-%m-%d %H:%M") if parsed else str(synced_at)
            items.append(f"• {title} — `{display_time}`")
        lines.append(f"| **{escape_cell(name)}（{len(episodes)} 份）** | {'<br>'.join(items)} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    manifest = json.loads(Path(arguments.manifest).read_text(encoding="utf-8"))
    output = Path(arguments.output)
    output.write_text(render_markdown(manifest), encoding="utf-8")
    groups = groups_from(manifest)
    print(json.dumps({"podcast_groups": len(groups), "episode_items": sum(len(items) for items in groups.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
