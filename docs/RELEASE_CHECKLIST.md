# Local Studio v1 Release Checklist

## Automated checks

```bash
npm run doctor
npm run test
npm run dev
```

保持项目运行，在另一个终端执行：

```bash
npm run smoke
```

有已下载的本地视频时，再执行更完整的媒体检查：

```bash
SMOKE_VIDEO_ID=<视频编号> npm run smoke
```

## Browser smoke path

1. “采访发现”：切换日期，确认来源状态、封面、原始链接和下载按钮。
2. “处理任务”：确认历史任务、进度、失败原因、重试和“打开剪辑”。
3. “剪辑工作台”：确认视频播放、字幕搜索、片段选择、序列审片和导出预检。
4. 刷新页面：确认日期、视图、当前视频、播放位置和未提交草稿恢复。
5. 分别检查桌面宽度和 390px 手机宽度，确保没有横向溢出或弹窗遮挡。
6. 导出一个 5 秒版本，用 FFprobe 检查时长、画幅、视频和音频流，并抽帧确认字幕或 Logo。

## Clean checkout

从当前提交导出一个不含 `.env`、依赖目录和 `storage` 的全新目录，然后运行：

```bash
npm run doctor
npm run setup
npm run test
```

确认 `.env` 会从 `.env.example` 创建，后端和前端依赖会安装，测试和生产构建通过。Docker 可用的机器再运行 `docker compose config` 和 `docker compose up --build`；没有 Docker 时应在发布记录中明确注明未实际构建容器。

## Known boundaries

- YouTube API key、OpenAI key 和平台登录态不能自动获取或随仓库分发。
- OpenCLI 可视浏览器仅适用于原生启动，Docker 模式使用 API 或下载器回退。
- v1 是单用户本地工作室，不包含登录、付费、协作、复杂时间线或自动发布。
