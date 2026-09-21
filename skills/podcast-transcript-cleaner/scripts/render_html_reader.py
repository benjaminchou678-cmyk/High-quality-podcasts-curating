#!/usr/bin/env python3
"""Render a self-contained weekly podcast HTML reader from a public manifest."""

import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlparse

PALETTE = [
    ("#edf7f5", "#c5ddd8", "#176b65"),
    ("#eef4fb", "#c9d9ea", "#315f91"),
    ("#fff5e9", "#ead2ae", "#9a5b17"),
    ("#f4effa", "#d9cbea", "#704a92"),
    ("#f9f1f1", "#e7cccc", "#915151"),
    ("#eef7ed", "#cbe0c8", "#4d7b47"),
]


def esc(value):
    return html.escape(str(value or ""), quote=True)


def safe_url(value):
    value = str(value or "").strip()
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def stamp(seconds):
    seconds = max(0, int(float(seconds or 0)))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


def speaker_style(speaker):
    try:
        index = max(0, int(str(speaker)) - 1)
    except ValueError:
        index = 0
    background, border, ink = PALETTE[index % len(PALETTE)]
    alignment = "align-right" if index % 2 else "align-left"
    return alignment, f"--speaker-bg:{background};--speaker-border:{border};--speaker-ink:{ink}"


def load_blocks(root, episode):
    relative = episode.get("dialogue_path") or f"episodes/{episode['episode_id']}/transcript/dialogue.readable.json"
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("dialogue_path must stay inside the manifest directory")
    return json.loads(path.read_text(encoding="utf-8"))


def render(manifest_path, output_path):
    manifest_path = Path(manifest_path).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summaries = {item["episode_id"]: item for item in manifest.get("transcript_summary", [])}
    episodes = sorted(manifest.get("episodes", []), key=lambda item: item.get("published_at", ""))
    rows, sections = [], []

    for episode in episodes:
        episode_id = episode["episode_id"]
        summary = summaries.get(episode_id, {})
        anchor = f"tr-{episode_id}"
        episode_url = safe_url(episode.get("episode_url"))
        transcript_url = safe_url(episode.get("transcript_url"))
        local_markdown = episode.get("transcript_markdown")
        links = []
        if episode_url:
            links.append(f"<a class='external-link' href='{esc(episode_url)}' target='_blank' rel='noopener noreferrer'>原节目页 ↗</a>")
        if transcript_url:
            links.append(f"<a class='external-link' href='{esc(transcript_url)}' target='_blank' rel='noopener noreferrer'>播客逐字稿 ↗</a>")
        elif local_markdown:
            links.append(f"<a class='external-link' href='{esc(local_markdown)}'>播客逐字稿</a>")
        link_html = "".join(links)
        coverage = summary.get("duration_coverage_ratio")
        confidence = summary.get("mean_confidence")
        speaker_count = summary.get("speaker_count")
        risk_level = summary.get("risk_level", "unknown")
        coverage_text = f"{coverage:.1%}" if isinstance(coverage, (int, float)) else "—"
        confidence_text = f"{confidence:.1%}" if isinstance(confidence, (int, float)) else "—"
        speaker_text = f"{speaker_count} 个声纹" if isinstance(speaker_count, int) and speaker_count > 0 else "声纹数未知"
        rows.append(
            "<tr>"
            f"<td>{esc(str(episode.get('published_at', ''))[:10])}</td>"
            f"<td>{esc(episode.get('podcast_name'))}</td>"
            f"<td><a class='transcript-link' href='#{anchor}' data-target='{anchor}'>{esc(episode.get('title'))}</a>"
            f"<div class='links'>{link_html}</div></td>"
            f"<td>{coverage_text}</td><td>{confidence_text}</td>"
            f"<td><span class='ok'>对话人分区已完成</span><small>{esc(speaker_text)} · {esc(risk_level)}</small></td></tr>"
        )
        turns = []
        for block in load_blocks(root, episode):
            speaker = str(block.get("speaker") or "未确定")
            label = "说话人未确定" if speaker == "未确定" else f"说话人{speaker}"
            alignment, style = speaker_style(speaker)
            turns.append(
                f"<article class='turn {alignment}' data-speaker='{esc(speaker)}' style='{style}'>"
                f"<div class='who'><b>{esc(label)}</b><span>{stamp(block.get('start_time'))}–{stamp(block.get('end_time'))}</span></div>"
                f"<p>{esc(block.get('text'))}</p></article>"
            )
        sections.append(
            f"<details class='transcript' id='{anchor}'><summary><span>{esc(episode.get('podcast_name'))}</span>"
            f"<strong>{esc(episode.get('title'))}</strong><small>{esc(str(episode.get('published_at', ''))[:10])} · 点击展开/收起</small>"
            f"</summary><div class='transcript-tools'>{link_html}</div>"
            "<div class='speaker-note'>说话人编号仅代表本文内不同声纹分区，不对应真实身份；实际对话者可能为 2 人、3 人或更多。</div>"
            f"<div class='dialogue'>{''.join(turns)}</div></details>"
        )

    sources = manifest.get("sources", [])
    source_rows = "".join(
        f"<tr><td>{esc(item.get('name'))}</td><td>{esc(item.get('status'))}</td><td>{item.get('episode_count', 0)}</td></tr>"
        for item in sources
    )
    start = manifest.get("range", {}).get("start", "")
    end = manifest.get("range", {}).get("end_exclusive", "")
    successful = sum(item.get("status") == "success" for item in sources)
    completed = sum(item.get("status") == "asr_transcript_generated" for item in manifest.get("transcript_summary", []))
    publication_note = manifest.get(
        "publication_note",
        "本页由公开 manifest 与清洗后对话数据生成，不包含音频或私有任务记录。",
    )
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>播客周采集与逐字稿</title><style>
:root{{--ink:#18202a;--muted:#65717d;--line:#dfe5e8;--accent:#176b65;--soft:#edf7f5}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;background:#f6f7f8;color:var(--ink);margin:0}}main{{max-width:1080px;margin:auto;padding:28px 18px 60px}}h1{{font-size:26px}}.kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}}.k{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;min-width:140px}}.n{{font-size:25px;font-weight:700;color:var(--accent)}}.l,small{{font-size:12px;color:var(--muted)}}.note,.speaker-note{{padding:12px 14px;background:#fff8e8;border-left:4px solid #d89a2b;margin:16px 0}}.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;margin:12px 0 24px}}th,td{{padding:10px;border-bottom:1px solid #edf0f2;text-align:left;vertical-align:top;font-size:13px}}th{{background:var(--soft)}}a{{color:var(--accent);font-weight:600;text-decoration:none}}a:hover{{text-decoration:underline}}.links,.transcript-tools{{display:flex;flex-wrap:wrap;gap:12px}}.links{{margin-top:7px}}.external-link{{display:inline-block;padding:4px 8px;border:1px solid #c8d9d6;border-radius:7px;background:#fff;font-size:12px}}.ok{{color:#176b65;white-space:nowrap;display:block}}.ok+small{{display:block;margin-top:4px}}.transcript{{background:#fff;border:1px solid var(--line);border-radius:12px;margin:12px 0;scroll-margin-top:12px;overflow:hidden}}.transcript[open]{{border-color:#8bc8bd}}summary{{cursor:pointer;padding:15px;display:flex;gap:8px;flex-direction:column}}summary span{{font-size:12px;color:var(--muted)}}summary strong{{font-size:15px;line-height:1.5}}.transcript-tools{{padding:11px 15px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:#fafcfc}}.speaker-note{{margin:12px 15px;font-size:12px}}.dialogue{{padding:8px 15px 20px}}.turn{{max-width:88%;border-radius:12px;padding:10px 12px;margin:10px 0;border:1px solid var(--speaker-border);background:var(--speaker-bg)}}.turn.align-left{{margin-right:auto}}.turn.align-right{{margin-left:auto}}.who{{display:flex;justify-content:space-between;gap:12px;font-size:12px;margin-bottom:6px}}.who b{{color:var(--speaker-ink)}}.who span{{color:var(--muted)}}.turn p{{font-size:14px;line-height:1.7;margin:0;white-space:pre-wrap}}@media(max-width:700px){{main{{padding:18px 10px 40px}}th,td{{font-size:12px;padding:8px}}.turn{{max-width:96%}}}}
</style></head><body><main><h1>播客周采集与逐字稿</h1>
<p>{esc(str(start).replace('T', ' '))} 至 {esc(str(end).replace('T', ' '))}（结束不含）</p>
<div class="kpis"><div class="k"><div class="n">{successful}/{len(sources)}</div><div class="l">RSS 来源成功</div></div><div class="k"><div class="n">{len(episodes)}</div><div class="l">区间内单集</div></div><div class="k"><div class="n">{completed}/{len(episodes)}</div><div class="l">逐字稿完成</div></div></div>
<div class="note">{esc(publication_note)}</div>
<h2>单集与逐字稿</h2><div class="table-wrap"><table><tr><th>日期</th><th>节目</th><th>单集</th><th>覆盖</th><th>平均置信度</th><th>状态</th></tr>{''.join(rows)}</table></div>
<h2>逐字稿正文</h2>{''.join(sections)}
<h2>来源状态</h2><div class="table-wrap"><table><tr><th>节目</th><th>状态</th><th>单集数</th></tr>{source_rows}</table></div>
</main><script>(function(){{function openTarget(id){{var target=document.getElementById(id);if(target){{target.open=true;setTimeout(function(){{target.scrollIntoView({{behavior:'smooth',block:'start'}});}},20);}}}}document.addEventListener('click',function(event){{var link=event.target.closest('.transcript-link');if(link)openTarget(link.getAttribute('data-target'));}});if(location.hash)openTarget(location.hash.slice(1));}})();</script></body></html>"""
    output_path = Path(output_path)
    output_path.write_text(page, encoding="utf-8")
    return {"episodes": len(episodes), "html_bytes": output_path.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    print(json.dumps(render(arguments.manifest, arguments.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
