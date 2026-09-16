# 输入与 manifest 结构

## `sources.json`

```json
[
  {
    "id": "example-show",
    "name": "示例播客",
    "feed_url": "https://example.com/feed.xml"
  }
]
```

要求：

- `id` 在当前配置内唯一，使用小写字母、数字和连字符。
- `name` 是报告中的规范节目名。
- `feed_url` 必须是公开 HTTP/HTTPS 地址。

## `manifest.json`

脚本输出的核心字段：

```json
{
  "range": {
    "start": "2026-09-07T00:00:00+08:00",
    "end_exclusive": "2026-09-14T00:00:00+08:00"
  },
  "generated_at": "...",
  "sources": [],
  "episodes": []
}
```

`episodes[]` 包含：

- `episode_id`：稳定机器标识，用于幂等与去重，不作为默认目录名
- `folder_name`：可读目录名，格式为 `YYYY-MM-DD_节目名_简短标题`；同名时才追加短标识
- `source_id`
- `podcast_name`
- `title`
- `published_at`
- `episode_url`
- `audio_url`
- `duration`
- `rss_transcript_candidates`
- `transcript_status`

任何运行环境特有的文档 token、绝对路径或认证信息都不应写入公开 manifest。
