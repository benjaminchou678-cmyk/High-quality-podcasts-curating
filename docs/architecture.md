# 架构与数据流

```text
公开 RSS
  ↓ 日期过滤 [start, end)
单集 metadata + shownotes
  ↓ 逐字稿来源优先级
RSS transcript → 公开节目页 → 公开音频 ASR
  ↓ 原始证据层（不覆盖）
segments.raw.json + transcript.meta.json
  ↓ 确定性清洗
合并同 speaker / 完全重复去除 / 标点规范 / 章节插入
  ↓
transcript.readable.md + dialogue.readable.json + quality-report.json
  ↓
weekly-report.md + weekly-report.html
```

## 关键设计

### 1. 证据与阅读分层

原始分段是可追溯证据，清洗结果另存为新文件。任何修订都不回写原始 ASR。

### 2. 半开时间区间

周采集统一使用 `[start, end)`，避免跨周边界重复收录同一单集。

### 3. 风险标记而非拦截

低覆盖、低置信、speaker 缺失或时间戳异常都会反映在质量报告和阅读稿头部，但不会静默丢弃文档。

### 4. 多说话人而非双人假设

speaker 标签可为 1、2、3 或更多。编号只在单篇逐字稿内有意义，不对应真实身份。

### 5. 发布边界

GitHub 演示只包含：

- Skill 规则与标准库脚本；
- 脱敏结构数据；
- 短 Markdown 示例与质量报告；
- 自包含 HTML 阅读版。

不包含：音频、完整原始 ASR、内部文档 token、企业账号信息、凭据和运行环境绝对路径。
