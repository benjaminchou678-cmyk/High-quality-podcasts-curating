# High-quality podcasts curating

一个基于真实公开来源、可复用的播客周采集与逐字稿清洗项目。

仓库包含两部分能力：

1. `podcast-weekly-collector`：按自然周读取 11 个公开 RSS，定位新单集，并按“RSS 逐字稿 → 公开节目页 → 公开音频 ASR”顺序取得逐字稿。
2. `podcast-transcript-cleaner`：保留原始证据，执行确定性轻编辑、多说话人分区、正文内阶段标题和质量风险标记，生成 Markdown、JSON 与 HTML 阅读版。

## 已包含的真实案例

`examples/2026-09-07至2026-09-13_真实周报与逐字稿/` 是一次完整真实试跑的公开副本：

- 11 个公开 RSS 来源全部读取成功；
- 自然周内发现 6 个单集，来自 5 个节目；
- 6 篇清洗后完整 Markdown 逐字稿；
- 6 份质量报告和 6 份可读对话 JSON；
- 真实周报 Markdown 与自包含 HTML 阅读版；
- 3 篇质量状态为 `normal`，3 篇为 `notice`；
- 系统支持 2、3、4 人及更多说话人分区；本次 6 篇最终清洗阅读版均归并为 2 个稳定声纹。

这些文档保留公开节目页、时间戳、阶段标题和说话人编号；不包含音频文件、私有 ASR 任务记录、内部文档 token、账号信息或本地绝对路径。

## 11 个公开来源

| 节目 | RSS |
|---|---|
| 42章经 | <https://feed.xyzfm.space/evgg6xle9rdc> |
| Lex Fridman Podcast | <https://lexfridman.com/feed/podcast/> |
| 高能量 | <https://feed.xyzfm.space/jhfuba3dahq8> |
| 硅谷101 | <https://feeds.fireside.fm/sv101/rss> |
| 乱翻书 | <https://feed.xyzfm.space/yxuruh3f9mc4> |
| 十字路口Crossing | <https://feed.xyzfm.space/68fyjknth9hj> |
| 晚点聊 LateTalk | <https://feeds.fireside.fm/latetalk/rss> |
| 卫诗婕｜漫谈Light the Star | <https://feed.xyzfm.space/4jjdlpq3khc9> |
| 小Lin说 | <https://feed.xyzfm.space/mkkxu98dm89e> |
| 张小珺Jùn｜商业访谈录 | <https://feed.xyzfm.space/dk4yh3pkpjp3> |
| 知行小酒馆 | <https://feed.xyzfm.space/j8yp8gxkmgqr> |

同一配置同时保存在：

- `examples/sources.json`
- `skills/podcast-weekly-collector/assets/default-sources.json`

## 输出载体选择

逐字稿清洗 Skill 支持两个输出接口：

- **飞书文档**：创建或原地更新飞书逐字稿，适合团队阅读与归档。
- **Markdown 文件**：生成可移植 `.md` 文件，适合 GitHub、版本管理和本地阅读。
- **两者都要**：基于同一权威内容同时生成，保持标题、风险状态、阶段标题、说话人顺序和正文一致。

如果用户没有明确指定，Skill 会在执行前主动询问选择“飞书文档 / Markdown / 两者”，不会擅自决定。

## 目录

```text
.
├── skills/
│   ├── podcast-weekly-collector/
│   │   ├── SKILL.md
│   │   ├── assets/default-sources.json
│   │   ├── references/input-schema.md
│   │   └── scripts/fetch_week.py
│   └── podcast-transcript-cleaner/
│       ├── SKILL.md
│       ├── references/format-and-risk.md
│       └── scripts/
│           ├── clean_transcript.py
│           ├── render_html_reader.py
│           └── render_weekly_trace.py
├── examples/
│   ├── README.md
│   ├── sources.json
│   └── 2026-09-07至2026-09-13_真实周报与逐字稿/
│       ├── manifest.json
│       ├── weekly-report.md
│       ├── weekly-report.html
│       └── episodes/
│           └── YYYY-MM-DD_节目名_简短标题/
│               ├── metadata.json
│               └── transcript/
│                   ├── transcript.readable.md
│                   ├── dialogue.readable.json
│                   └── quality-report.json
└── docs/architecture.md
```

## 查看真实演示

- [真实周报 Markdown](examples/2026-09-07至2026-09-13_真实周报与逐字稿/weekly-report.md)
- [真实周报 HTML](examples/2026-09-07至2026-09-13_真实周报与逐字稿/weekly-report.html)
- [6 篇完整逐字稿索引](examples/README.md)

GitHub 默认不会直接执行 HTML，可下载后在浏览器打开；页面完全自包含，不依赖外部脚本或样式。

## 重新生成 HTML

```bash
python3 skills/podcast-transcript-cleaner/scripts/render_html_reader.py \
  examples/2026-09-07至2026-09-13_真实周报与逐字稿/manifest.json \
  --output examples/2026-09-07至2026-09-13_真实周报与逐字稿/weekly-report.html
```

## 使用默认 11 个来源采集

```bash
python3 skills/podcast-weekly-collector/scripts/fetch_week.py \
  --sources skills/podcast-weekly-collector/assets/default-sources.json \
  --start 2026-09-07T00:00:00+08:00 \
  --end 2026-09-14T00:00:00+08:00 \
  --output ./output
```

采集脚本负责公开 RSS 下载、日期筛选、字段提取和目录生成。ASR 是可替换外部通道，需要运行环境提供能够返回时间戳、置信度和 speaker 字段的服务。

## 清洗单集

```bash
python3 skills/podcast-transcript-cleaner/scripts/clean_transcript.py <episode-dir>
```

输入目录需要包含 `metadata.json`、`shownotes.raw.txt`（可选）、`transcript/segments.raw.json` 和 `transcript/transcript.meta.json`。

## 数据与使用边界

- 逐字稿均由 ASR 生成，未经人工校对，不应作为原节目官方文稿。
- 说话人编号只代表单篇文稿中的不同声纹，不推断真实身份。
- 质量风险只标记，不阻止文档生成；使用前请结合原节目复核。
- 本仓库不分发音频文件；音频和节目内容的权利归原权利人所有。
- RSS、节目页和逐字稿应依据来源站点条款、版权规则及合理使用边界使用。
- MIT License 仅覆盖本仓库的原创代码和项目说明；节目内容与机器逐字稿的权利边界见 [`NOTICE.md`](NOTICE.md)。
