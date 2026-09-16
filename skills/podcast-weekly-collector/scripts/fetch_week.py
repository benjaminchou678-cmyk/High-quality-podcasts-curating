#!/usr/bin/env python3
"""Fetch public podcast RSS feeds for a configurable half-open date range."""

import argparse
import datetime as dt
import email.utils
import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "podcast-weekly-collector/1.0 (+public-demo)"


def local(tag):
    return tag.split("}", 1)[-1].lower()


def require_public_url(value):
    parsed = urlparse(str(value or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid public URL: {value!r}")
    return value


def child_text(node, names):
    names = {name.lower() for name in names}
    for child in list(node):
        if local(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def parse_iso(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("date range values must include a timezone")
    return parsed


def parse_date(value, timezone):
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(timezone)
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(timezone)
    except ValueError:
        return None


def fetch(url, tries=3):
    last_error = None
    for attempt in range(tries):
        try:
            request = urllib.request.Request(
                require_public_url(url),
                headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, text/xml, */*"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read(), response.geturl()
        except Exception as error:  # network errors are recorded per source
            last_error = error
            if attempt + 1 < tries:
                time.sleep(1.5 * (attempt + 1))
    raise last_error


def episode_nodes(root):
    items = [node for node in root.iter() if local(node.tag) == "item"]
    return items or [node for node in root.iter() if local(node.tag) == "entry"]


def extract_link(item):
    direct = child_text(item, {"link"})
    if direct:
        return direct
    for child in list(item):
        if local(child.tag) == "link" and child.attrib.get("rel", "alternate") in {"", "alternate"}:
            if child.attrib.get("href"):
                return child.attrib["href"]
    return ""


def extract_audio(item):
    for child in list(item):
        if local(child.tag) == "enclosure" and child.attrib.get("url"):
            return child.attrib["url"]
        if local(child.tag) == "link" and child.attrib.get("rel") == "enclosure" and child.attrib.get("href"):
            return child.attrib["href"]
    return ""


def transcript_candidates(item):
    candidates = []
    for child in item.iter():
        if local(child.tag) != "transcript":
            continue
        url = child.attrib.get("url") or child.attrib.get("href") or (child.text or "").strip()
        if url:
            candidates.append({
                "url": url,
                "type": child.attrib.get("type", ""),
                "language": child.attrib.get("language", ""),
            })
    deduplicated = []
    seen = set()
    for candidate in candidates:
        if candidate["url"] not in seen:
            seen.add(candidate["url"])
            deduplicated.append(candidate)
    return deduplicated


def duration_text(item):
    for child in item.iter():
        if local(child.tag) == "duration" and child.text:
            return child.text.strip()
    return ""


def stable_id(source_id, guid, link, audio, title):
    identity = guid or link or audio or title
    return hashlib.sha256(f"{source_id}|{identity}".encode("utf-8")).hexdigest()[:16]


def validate_sources(sources):
    ids = set()
    for source in sources:
        source_id = str(source.get("id", ""))
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source_id):
            raise ValueError(f"invalid source id: {source_id!r}")
        if source_id in ids:
            raise ValueError(f"duplicate source id: {source_id}")
        ids.add(source_id)
        require_public_url(source.get("feed_url"))
        if not source.get("name"):
            raise ValueError(f"source name is required: {source_id}")


def run(sources_path, start_value, end_value, output):
    start = parse_iso(start_value)
    end = parse_iso(end_value)
    if end <= start:
        raise ValueError("--end must be later than --start")
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    if not isinstance(sources, list):
        raise ValueError("sources file must contain a JSON array")
    validate_sources(sources)

    output = Path(output)
    for directory in (output, output / "rss", output / "source-status", output / "episodes"):
        directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "range": {"start": start.isoformat(), "end_exclusive": end.isoformat()},
        "generated_at": dt.datetime.now(start.tzinfo).isoformat(),
        "sources": [],
        "episodes": [],
    }

    for source in sources:
        status = {
            "id": source["id"], "name": source["name"], "feed_url": source["feed_url"],
            "status": "failed", "episode_count": 0,
        }
        try:
            raw, final_url = fetch(source["feed_url"])
            (output / "rss" / f"{source['id']}.xml").write_bytes(raw)
            root = ET.fromstring(raw)
            selected = []
            parse_failures = []
            for item in episode_nodes(root):
                title = child_text(item, {"title"})
                raw_date = child_text(item, {"pubdate", "published", "updated", "date"})
                published = parse_date(raw_date, start.tzinfo)
                if published is None:
                    parse_failures.append({"title": title, "date_raw": raw_date})
                    continue
                if not start <= published < end:
                    continue
                guid = child_text(item, {"guid", "id"})
                episode_url = extract_link(item)
                audio_url = extract_audio(item)
                description = child_text(item, {"description", "summary", "encoded", "content"})
                episode_id = stable_id(source["id"], guid, episode_url, audio_url, title)
                episode_dir = output / "episodes" / episode_id
                episode_dir.mkdir(exist_ok=True)
                candidates = transcript_candidates(item)
                metadata = {
                    "episode_id": episode_id,
                    "source_id": source["id"],
                    "podcast_name": source["name"],
                    "title": title,
                    "published_at": published.isoformat(),
                    "published_raw": raw_date,
                    "guid": guid,
                    "episode_url": episode_url,
                    "audio_url": audio_url,
                    "duration": duration_text(item),
                    "rss_transcript_candidates": candidates,
                    "transcript_status": "rss_candidate_found" if candidates else "needs_transcript_discovery",
                }
                (episode_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
                (episode_dir / "shownotes.raw.txt").write_text(description, encoding="utf-8")
                manifest["episodes"].append(metadata)
                selected.append(metadata)
            status.update({
                "status": "success", "final_feed_url": final_url, "episode_count": len(selected),
                "date_parse_failure_count": len(parse_failures), "date_parse_failures": parse_failures[:10],
            })
        except Exception as error:
            status["error"] = f"{type(error).__name__}: {error}"
        (output / "source-status" / f"{source['id']}.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["sources"].append(status)

    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "sources": len(sources),
        "source_success": sum(item["status"] == "success" for item in manifest["sources"]),
        "episodes": len(manifest["episodes"]),
        "output": str(output),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.sources, arguments.start, arguments.end, arguments.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
