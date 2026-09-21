# 安装指南

## 一、下载仓库

有 Git：

```bash
git clone https://github.com/benjaminchou678-cmyk/High-quality-podcasts-curating.git
cd High-quality-podcasts-curating
```

没有 Git：在 GitHub 仓库点击 `Code` → `Download ZIP`，解压后进入目录。

## 二、确认 Skill 安装目录

不要盲目假设固定路径。目标应是该 Agent 环境实际加载的、路径以 `workspace/.user_skills` 结尾的目录。

常见做法：

1. 在 Agent 的 Skill 列表或设置中找到一个已安装用户 Skill。
2. 查看其路径，定位同级 `.user_skills` 目录。
3. 将本仓库 `skills/` 下的两个完整目录复制进去。

目录结果应类似：

```text
<实际工作区>/workspace/.user_skills/
├── podcast-weekly-collector/
│   ├── SKILL.md
│   ├── assets/
│   ├── references/
│   └── scripts/
└── podcast-transcript-cleaner/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

不要只复制 `SKILL.md`；脚本、references 和 assets 都是 Skill 的一部分。

## 三、使用安装脚本

Linux / macOS：

```bash
export USER_SKILLS_DIR="/实际路径/workspace/.user_skills"
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR"
```

首次安装预演，不写文件：

```bash
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR" --dry-run
```

目标中已存在同名 Skill 时，脚本默认停止，避免覆盖同事自己的修改。升级预演需要显式声明覆盖意图：

```bash
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR" --dry-run --overwrite
```

确认后执行：

```bash
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR" --overwrite
```

脚本不会写入仓库以外的其他目录，不安装第三方依赖，也不写入账号凭据。

## 四、重启或刷新 Agent

复制完成后：

1. 重启 Agent / 新建会话，或在平台中执行“重新加载 Skills”。
2. 检查 Skill 列表是否出现：
   - `podcast-weekly-collector`
   - `podcast-transcript-cleaner`
3. 可用以下请求测试触发：

```text
请抓取上一个自然周的播客，并在开始逐字稿处理前询问我输出为飞书文档、Markdown 还是两者。
```

## 五、运行前检查

```bash
python3 scripts/check_environment.py
```

检查项包括：

- Python 版本；
- 两个 Skill 是否完整；
- 23 个 RSS 配置是否可解析；
- 可选的 Git、GitHub CLI；
- 可选 ASR / 飞书通道提示。

该脚本只做本地只读检查，不联网、不登录，也不会验证真实服务权限。

## 六、能力分级

| 能力 | 仅安装仓库即可 | 额外要求 |
|---|---:|---|
| 读取公开 RSS | 是 | 网络可以访问 RSS |
| 筛选某个自然周单集 | 是 | Python 3.10+ |
| 使用 RSS 已提供的逐字稿 | 是 | 来源确实提供逐字稿 |
| 从音频生成逐字稿 | 否 | ASR 工具/API/平台能力 |
| 时间戳 | 不一定 | ASR 必须返回起止时间 |
| 置信度 | 不一定 | ASR 必须返回 confidence |
| 说话人分区 | 不一定 | ASR 必须支持 diarization/speaker info |
| 输出 Markdown | 是 | 本地文件写入能力 |
| 输出飞书文档 | 否 | 飞书文档工具、登录和目标目录权限 |

## 七、升级

拉取新版本后重新运行安装脚本：

```bash
git pull
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR" --dry-run --overwrite
python3 scripts/install_skills.py --target "$USER_SKILLS_DIR" --overwrite
```

升级前建议备份同事在 Skill 目录中的自定义修改。

## 八、常见问题

### Skill 能看到，但不能转写音频

这是最常见情况：Skill 已安装，但运行环境没有 ASR 通道。可以：

- 使用 RSS 或节目页已有逐字稿；
- 接入平台自带音频转写工具；
- 接入公开云 ASR API；
- 本地运行 Whisper 类模型后，把结果转换为规定的 `segments.raw.json`。

### 能转文字，但没有说话人标签

普通语音识别与说话人分区是两项能力。需要 ASR 支持 `speaker diarization`，或增加独立的说话人分区步骤。缺少 speaker 时 Skill 会保留正文并标记复核风险。

### 不能写飞书

确认 Agent 是否具备飞书在线文档工具、是否已登录、是否有目标文件夹编辑权限。若没有，可选择 Markdown 输出，不影响清洗本身。

### GitHub 中 HTML 不能直接运行

GitHub 文件页只展示 HTML 源码。下载后在浏览器打开，或部署到 GitHub Pages。
