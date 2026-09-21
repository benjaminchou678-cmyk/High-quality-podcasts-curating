# 说话人模式与编号规范

## 目标

- 单人节目只使用 `说话人1`，不因 ASR 短暂抖动制造额外说话人。
- 多人节目按稳定声纹区分 `说话人1`、`说话人2`、`说话人3`……，不设置人数上限。
- 编号只表示当前文稿内的声纹分区，不推断真实身份。

## 元数据模式

`metadata.json` 可选：

```json
{
  "speaker_mode": "single"
}
```

允许值：`single`、`multi`、`auto`；省略时为 `auto`。

兼容字段：

- `single_speaker: true` 等同 single。
- `expected_speaker_count: 1` 等同 single。
- `expected_speaker_count > 1` 用于核对，不限制实际人数。

## 判定优先级

1. 用户明确说明。
2. 元数据模式字段。
3. 可靠官方材料明确说明节目形态。
4. auto：一个非空标签为 single；两个及以上为 multi；没有标签为 unknown。

不得仅凭节目名、主播数量或 Shownotes 人名数量猜测。

## 编号归一

- single：所有非空正文统一为 `speaker = "1"`。
- multi：按原始 speaker 标签首次出现顺序连续映射为 `"1"`、`"2"`、`"3"`……。
- 原始标签可为数字、字母或 UUID，展示层不直接暴露。
- 缺失 speaker 保留 `未确定`，不得轮流分配或依据语义猜测。
- 人数不设上限，不把 3 人以上压缩为双人。

## 防误判

- multi 中出现稀有新声纹时不自动合并，记录 `rare_speaker_cluster`。
- single 中 ASR 返回多个声纹时统一为说话人1，同时记录 `single_mode_collapsed_clusters`。
- `expected_speaker_count` 与归一数量不符时记录 `speaker_count_mismatch`，但继续生成。
- 重叠发言无法可靠拆分时标记 `[多人同时发言]`。

## 质量指标

记录：

- `speaker_mode_requested`
- `speaker_mode_resolved`
- `raw_speaker_count`
- `normalized_speaker_count`
- `raw_missing_speaker_ratio`
- `speaker_segment_counts`
- `speaker_remap`

## 完成检查

- single 正文只能出现说话人1。
- multi 编号从 1 连续递增，不跳号、不限最大值。
- 相同原始标签始终映射到同一编号。
- 不同标签不得无证据合并。
- JSON、Markdown 和飞书使用同一归一编号。
