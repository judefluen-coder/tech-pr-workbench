# Tech PR Workbench

Tech PR Workbench 是一个本地运行的 AI/科技采访日报与剪辑工作台，面向科技公司 PR、内容运营和创始人办公室。它每天帮你发现 AI 圈新采访，保留原始链接，识别采访嘉宾，生成中文摘要；当你选择某条视频后，可以下载授权素材、生成中文字幕、挑选高光片段，并导出带字幕的剪辑序列视频。

> 默认定位：个人或小团队本地工具。请只下载、剪辑和再发布你有权处理的素材。

## 你可以用它做什么

- 按日期区间抓取 AI 采访候选：YouTube 优先，B 站补充。
- 看每条视频的标题、来源、发布时间、人物识别、摘要和原始链接。
- 点击“下载并翻译”后，自动尝试下载视频、拉取字幕、生成中文字幕。
- 在剪辑工作台里看视频、读中文字幕、查看推荐高光、组合多段剪辑。
- 导出 VTT/SRT 字幕、剪辑表 CSV，以及带中文字幕的序列视频。

## 截图导览

### 1. AI 采访日报

![AI interview daily dashboard](docs/screenshots/daily-dashboard.jpg)

这个页面用于每天判断“有哪些视频值得进入下一步”：

- 顶部日期区间：选择要看的日期，例如昨天，或 6 月 1 日到 6 月 13 日。
- 抓取按钮：运行 YouTube/B 站发现流程，刷新候选采访。
- 数据概览：显示候选数量、可处理数量、处理中数量、已可剪辑数量。
- 来源状态：告诉你 YouTube、B 站、RSS 等来源当前是否可用。
- 视频列表：逐条展示标题、来源、人物识别、摘要、观看量和时长。
- 操作按钮：打开原始链接，或点击“下载并翻译”进入处理流程。

人物标签有三类：

- `追踪：某人`：命中了你的重点人物池。
- `识别：某人`：系统从标题、简介或字幕中识别出的采访嘉宾。
- `人物待确认`：标题、简介和已有字幕里暂时没有明确嘉宾。

### 2. 剪辑工作台

![Clip workbench](docs/screenshots/clip-workbench.jpg)

这个页面用于把一条采访变成可发布素材：

- 视频播放器：播放已经下载到本地的视频。
- 中文字幕：下载翻译完成后，字幕会随视频时间同步。
- 时间线：显示系统推荐的高光片段、当前选区和已加入的剪辑序列。
- 入点/出点：像剪辑软件一样选择片段起点和终点。
- 高光建议：系统根据字幕中的观点词、AI 议题和表达密度推荐片段。
- 导出序列视频：把剪辑序列里的片段拼成一个 MP4，并尽量烧录中文字幕。

## 典型工作流

1. 打开 `http://127.0.0.1:5173`。
2. 选择日期区间，点击“抓取区间 AI 采访”。
3. 浏览候选列表，看摘要、人物标签和原始链接。
4. 对值得处理的视频点击“下载并翻译”。
5. 完成后进入剪辑工作台，查看中文字幕和高光建议。
6. 设入点/出点，或把推荐高光加入剪辑序列。
7. 点击“导出序列视频”，选择保存位置和文件名。

## 默认是否收费

默认配置不依赖额外付费 API：

- `yt-dlp`、FFmpeg、SQLite、Argos Translate、本地 Ollama 都是本机工具或开源软件，本项目不会向它们按量付费。
- YouTube Data API 用于发现公开视频元数据，主要受每日 quota 限制；默认配额可能不够大规模生产使用。
- OpenAI API 不参与默认流程，也不会默认安装 SDK。只有当你额外安装 `backend[cloud-ai]`、设置 `CLOUD_AI_ENABLED=true` 并提供 `OPENAI_API_KEY` 时，才会调用云端付费模型。
- GitHub 公共仓库可免费托管代码；如果你启用额外的私有团队、Actions 大量 CI、Packages 等能力，可能进入 GitHub 自身的计费范围。

## 平台支持

已在 macOS 本地开发和测试。Linux 通常可以直接运行。Windows 建议优先使用 WSL2；原生 Windows 也可以尝试，但需要确保依赖都在 PATH 中。

基础依赖：

- Node.js 20+
- uv
- FFmpeg

可选依赖：

- YouTube Data API key：提升 YouTube 发现稳定性。
- opencli：无 YouTube API key 时补充搜索。
- Ollama：本地大模型翻译备用。
- faster-whisper：没有字幕时做本地转写。

macOS 可用 Homebrew 安装基础依赖：

```bash
brew install node uv ffmpeg
```

## 快速启动

```bash
git clone https://github.com/judefluen-coder/tech-pr-workbench.git
cd tech-pr-workbench
npm run setup
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

`npm run setup` 会：

- 如果 `.env` 不存在，从 `.env.example` 复制一份。
- 安装后端依赖，包括本地翻译依赖。
- 安装前端依赖。

`npm run dev` 会同时启动：

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

## 配置

编辑 `.env`：

```env
YOUTUBE_API_KEY=
ARGOS_TRANSLATE_ENABLED=true
LOCAL_ASR_ENABLED=false
DOWNLOAD_ENGINE=yt-dlp
LOCAL_YTDLP_DISCOVERY=true
OPENCLI_DISCOVERY_ENABLED=true
BILIBILI_DISCOVERY_ENABLED=true
```

建议第一步先不配置 OpenAI。需要更稳定的 YouTube 发现结果时，再配置 `YOUTUBE_API_KEY`。

如果确实需要 OpenAI 作为云端转写/翻译兜底：

```bash
uv sync --project backend --extra cloud-ai
```

然后在 `.env` 中设置：

```env
CLOUD_AI_ENABLED=true
OPENAI_API_KEY=你的 key
```

如果需要本地 Whisper 转写：

```bash
uv sync --project backend --extra local-asr
```

然后在 `.env` 中设置：

```env
LOCAL_ASR_ENABLED=true
```

## 字幕和下载策略

点击“下载并翻译”后，系统按顺序尝试：

1. 下载原视频和可用字幕。
2. 如果已有中文字幕，直接导入。
3. 如果只有英文字幕，用本地翻译生成中文字幕。
4. 如果没有字幕，并且启用了本地 ASR 或云端 AI，再做转写和翻译。

导出序列视频时，系统会读取剪辑序列中的全部片段，拼接成一个 MP4，并尽量烧录中文字幕。

## 合规提醒

- 日报发现阶段只保存元数据和原始链接。
- 自动下载用于本地剪辑工作流，请确保你有权下载、编辑和导出该视频。
- 不要提交 `.env`、`storage/` 里的数据库、下载视频、导出视频或字幕文件。
- 如果平台条款或素材授权不允许下载，请只保留原始链接，或导入你已经获得授权的本地素材。

## 测试

```bash
npm run test
```

或分别运行：

```bash
npm run test:backend
npm run build:frontend
```

## 常见问题

### 没有 YouTube API key 能用吗？

能用，但发现覆盖率会下降。系统会尝试本机 opencli/yt-dlp 搜索和 B 站来源。要稳定追踪大量人物，建议配置 YouTube Data API key。

### 为什么有些视频显示“人物待确认”？

这表示标题、简介和已有字幕里没有明确采访嘉宾。下载翻译完成后，系统会用字幕再识别一次。

### 剪辑序列导出的是哪些视频？

导出序列视频会读取当前视频的剪辑序列，把你加入序列的所有片段按顺序拼接。没有加入序列的高光建议不会自动进入导出。

### 可以给非技术用户用吗？

可以作为本地工具使用。当前版本仍需要安装 Node.js、uv 和 FFmpeg；如果要完全给非技术同事使用，下一步建议做 macOS `.app` 或 Docker Desktop 一键包。
