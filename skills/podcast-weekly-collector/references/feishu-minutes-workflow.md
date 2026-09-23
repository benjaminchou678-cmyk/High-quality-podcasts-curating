# 飞书妙记主转写通道

## 目录

- 前置与输出边界
- 下载、上传与断点恢复
- 转写与 AI 总结分别就绪
- 导入、提要与原文档归档
- 失败兜底和清理

## 前置与输出边界

先复用同集可用全文；只有 RSS 与公开节目页均无全文时，才用飞书妙记，原 ASR 作为备选。读取当前环境的 `lark-drive`、`lark-meeting`，以及需生成豆包文档时的 `lark-doc`，按各自最新参考执行，不凭记忆拼参数。

- `output_targets` 含 `lark_doc`：音频和最终豆包逐字稿放原“01_按播客归档/节目名”，周报放原“02_按周归档/自然周”。已有文档复用原 URL，未选择或无法确认的文件夹先询问，不能自动写入根目录。
- 仅选择 `markdown`：默认不写任何飞书资源，改用已授权 ASR 或公开全文；用户另行明确授权“用妙记转写但只交付 MD”后才允许创建妙记，不据此创建豆包文档或改共享权限。
- 妙记对象不等同于 Drive 文件：音频所在文件夹不保证妙记自动归入该文件夹。原豆包文档作为稳定入口，附妙记回听链接；不得假称妙记继承共享文件夹权限。
- `archive_context` 保存于私有运行状态，沿用既有根目录、节目子目录、周目录及 `episode_id → document_url` 映射。运行前验证目标，禁止因新通道更换根目录或复制整棵目录。
- 文件须为支持的音频格式（wav、mp3、m4a、aac、ogg、wma、amr），不超过 6 小时及 6 GB；以当前平台规则为准。媒体格式、时长、大小和完整性都要实测，不能只验扩展名。
- 单集以节目 ID + RSS guid/规范节目 URL 去重，标题仅辅助核验；找到已有音频/妙记/逐字稿先验证匹配再复用。

## 下载、上传与断点恢复

只下载合法公开音频。先写 `.part`，成功核对后改为可读文件名；记录 URL、大小、SHA-256 与媒体时长。不得绕过访问限制，也不能将 `.part` 上传。

使用 `drive +upload` 上传到原节目文件夹，保存 `audio_file_token` 和返回的 `audio_file_url`。以下命令中的尖括号是说明用占位，执行时必须替换实际值并按需引用路径：

```bash
lark-cli minutes +upload --file-token <audio_file_token>
```

成功即保存 `minute_token`、`minute_url`，只创建一次。上传成功但创建失败从 file token 续作；创建请求超时状态不明时先查重，不重复上传或创建。

在 Git 忽略的 `runtime.private.json` 中，按单集维护一个权威状态记录：

```text
stage: discovered → audio_uploaded → minutes_submitted → transcript_ready
       → digest_ready → archived → verified
minutes_summary_status: pending | updated | failed
archive_status: pending | verified | failed
attempts / last_error / next_action
archive_context / audio_file_token / minute_token / document_url
```

这些字段是编排约定，不是 CLI 返回协议；成功阶段只能在对应响应及回读后推进。摘要写回失败不能被误报成音频转写失败。下载/上传/轮询由 Agent 通过现有工具执行，两个 Python 辅助脚本只负责转换与渲染，不宣称一条命令自动执行所有外部操作。

## 转写与 AI 总结分别就绪

```bash
lark-cli minutes +detail --minute-tokens <minute_token> --wait-ready --transcript --chapter --summary --format json
```

确认导出的 Transcript 非空且首尾匹配单集；Summary 和 Chapter 可能晚于 Transcript 就绪。默认总结为空不代表转写失败，更不能据此重做 ASR。

按服务端提示有上限轮询：每轮间隔不少于 15 秒，一次执行预算最多 20 次；到预算上限保存 `minute_token` 和下一动作，标为待续作，不删除、不重建、不启动并行 ASR。`quota_exceeded` 不重试；权限/登录阻塞按平台要求处理，用户拒绝授权后停止受影响操作。

如果缓存导出已存在，记录当前文件哈希，使用新的导出目录取得本次回读；不得将“transcript already exists”当作最新云端核验。新导出与旧证据分开保存。

## 导入、提要与原文档归档

完整读取 Transcript，不能用妙记默认 Summary、Shownotes 或章节说明充当正文。

```bash
python3 <collector-dir>/scripts/import_minutes_transcript.py \
  <transcript.txt> <episode-dir> \
  --minute-url <minute_url> --audio-file-url <audio_file_url>
```

此脚本：

- 原样保存 `minutes.transcript.raw.txt` 与 SHA-256；转换出 `segments.raw.json` 和 `transcript.meta.json`，来源为 `feishu_minutes`。
- 只接受当前支持的 `Speaker N HH:MM:SS.mmm` / `说话人N HH:MM:SS` TXT 结构；其他格式或异常明确报错并保留原文件，不静默丢弃。
- TXT 通常只有发言开始时间。结束字段使用下一开始时间/媒体时长作为**推算边界**，标 `end_time_estimated` 和 `end_time_basis`，不声称精确结束时间。
- 缺失置信度不填造；清洗时覆盖率及长静默指标置为 `null`，标风险，不从媒体总时长制造 100% 全文覆盖。
- 不依据推算边界去重或合并发言。已有任何证据文件即拒绝覆盖；重导入用独立 run 目录，原文档映射继续沿用。

完整阅读后按清洗 Skill 的 `references/topic-digest.md` 生成唯一 `topic-digest.json`：默认 3–8 个中文顶层议题、每个 1–6 个中文二级要点；短内容不凑数。每项时间证据从正文定位；专业名词可以保留英文，观点须保留归属、数字、否定和不确定性。不得翻译原语言正文。

```bash
python3 <collector-dir>/scripts/render_minutes_summary.py \
  <episode-dir>/transcript/topic-digest.json \
  --output <episode-dir>/transcript/minutes-summary.md
```

渲染器检查最多两层、显式有限时间值与中文文本；不是翻译服务。输出文件不覆盖输入或旧输出，重跑使用新文件名。

默认 AI 总结就绪后，先读取并保存原总结，再用 `minutes +summary --minute-token <minute_token> --summary @<summary-file>` 写回同一提要。只用标题、加粗和列表，不用链接、表格或代码块。写后回读并比对；仅在确认产物就绪状态变化后重试一次瞬时写入错误，仍失败标 `minutes_summary_status=failed`，保留正文继续生成豆包文档，不重做转写。

运行清洗脚本，然后按 `lark-doc` 创建/最小范围更新原豆包文档：中文提要 + 原语言全文 + 来源和质量风险。只在私有飞书输出开启 `include_private_links: true` 后附妙记回听链接；可公开的 Markdown 默认不包含内部链接。

- 豆包逐字稿仍在原节目文件夹，不用妙记替代最终文档。
- 周报仍在原自然周文件夹，按实际发布日期归周；踪迹主链接仍指向豆包逐字稿，而非节目页或妙记。
- 回读全部正文、提要、时间范围及链接，查询实际父目录，检查无重复。云盘音频存在不代表文档归档成功。
- 共享权限不擅自修改；读者能否打开妙记需独立验证，不能从豆包文档可见推断妙记可见。

## 失败兜底和清理

只有缺少妙记工具、媒体不兼容、额度不足或确认不可恢复的**转写失败**时，才进入 `asr-contract.md`；备用 ASR 须已授权。目标归档文件夹缺失或无权限不能通过 ASR 解决，需记录/询问；任何拒绝授权不可绕过。已取得正文但 Summary 写回失败，继续复用正文，不触发 ASR。

风险只标记不阻断归档；无法解析时保留原始文件并记录解析失败，不能把摘要冒充正文或把失败状态计为完成。

临时音频清理默认关闭。仅用户明确授权清理、确认文件是本任务下载的副本，且所选输出、妙记正文及回读均完成后，才删除该单个本地副本；不删除 Drive 音频、妙记、转写证据或其他用户文件。失败时保留恢复材料。

## 发布检查

只提交代码、规范和可公开示例。`runtime.private.json`、转写原始文件、媒体、真实文件夹/妙记/音频链接和凭据不进入 GitHub。完成报告分别说明转写、妙记总结、豆包文档、周报与校验状态，不能把部分完成说成全部完成。
