# High-quality podcasts curating

一个可公开复用的播客周采集与逐字稿清洗演示项目。

项目把完整流程拆成两个 Skill：

1. `podcast-weekly-collector`：按自然周读取 RSS，定位单集，并按“公开逐字稿 → 节目页 → 公开音频 ASR”顺序取得逐字稿。
2. `podcast-transcript-cleaner`：保留原始证据，执行确定性轻编辑、说话人分区、正文内阶段标题和质量风险标记，并生成 Markdown 与 HTML 阅读版。

## 目录

```text
.
├── skills/
│   ├── podcast-weekly-collector/
│   └── podcast-transcript-cleaner/
├── examples/
│   └── weekly-demo/
│       ├── manifest.json
│       ├── weekly-report.md
│       ├── weekly-report.html
│       └── episodes/demo-001/transcript/
└── docs/
    └── architecture.md
```

## 快速试跑

以下命令只读取 `examples/weekly-demo` 中的脱敏演示数据，不联网、不调用 ASR：

```bash
python3 skills/podcast-transcript-cleaner/scripts/clean_transcript.py \
  examples/weekly-demo/episodes/demo-001

python3 skills/podcast-transcript-cleaner/scripts/render_html_reader.py \
  examples/weekly-demo/manifest.json \
  --output examples/weekly-demo/weekly-report.html
```

采集 Skill 的公开脚本可用任意 RSS 配置和日期区间运行：

```bash
python3 skills/podcast-weekly-collector/scripts/fetch_week.py \
  --sources examples/sources.example.json \
  --start 2026-09-07T00:00:00+08:00 \
  --end 2026-09-14T00:00:00+08:00 \
  --output ./output
```

## 数据边界

- 不提交音频、原始完整 ASR、内部飞书 token、企业账号信息、内部绝对路径或凭据。
- `examples/` 是脱敏、缩短的结构演示，不是完整节目逐字稿。
- 机器转写风险只标记，不阻止产物生成和归档。
- 说话人编号仅表示同一文稿中的不同声纹，不推断真实身份。

## 依赖

核心脚本使用 Python 3 标准库。ASR 属于可替换的外部通道，需要运行环境自行提供能够返回时间戳、置信度和可选 speaker 字段的转写服务。
