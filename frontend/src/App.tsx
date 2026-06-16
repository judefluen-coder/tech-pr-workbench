import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import {
  ArrowSquareOut,
  CalendarBlank,
  CaretDown,
  CheckCircle,
  Clock,
  DownloadSimple,
  FileArrowDown,
  FilmSlate,
  GlobeHemisphereEast,
  LinkSimple,
  MagnifyingGlass,
  PlayCircle,
  PlusCircle,
  Scissors,
  SpinnerGap,
  Subtitles,
  Trash,
  WarningCircle,
} from "@phosphor-icons/react";
import { api } from "./lib/api";
import { formatDate, formatDuration, formatNumber, formatTimecode, statusLabel } from "./lib/format";
import type { ClipMark, ClipPayload, ClipRenderResult, DailyReport, Job, SourceRun, TopicTemplate, Transcript, Video } from "./types";

const PROCESSING_STATUSES = new Set(["queued", "running"]);
const VIDEO_PROCESSING_STATUSES = new Set(["downloading", "subtitle_fetching", "transcribing", "translating"]);
const DEFAULT_TEMPLATE_SLUG = "ai-interviews";

type TranscriptRow = ReturnType<typeof buildTranscriptRows>[number];

interface HighlightSuggestion {
  id: string;
  start: number;
  end: number;
  label: string;
  reason: string;
  quote: string;
  score: number;
}

function App() {
  const defaultRange = useMemo(() => defaultBeijingRange(), []);
  const [startDate, setStartDate] = useState(defaultRange.start);
  const [endDate, setEndDate] = useState(defaultRange.end);
  const [templates, setTemplates] = useState<TopicTemplate[]>([]);
  const [templateSlug, setTemplateSlug] = useState(() => window.localStorage.getItem("tech-pr-template") || DEFAULT_TEMPLATE_SLUG);
  const [report, setReport] = useState<DailyReport | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [clip, setClip] = useState<ClipPayload | null>(null);
  const [jobs, setJobs] = useState<Record<number, Job>>({});
  const [jobIdsByVideo, setJobIdsByVideo] = useState<Record<number, number>>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [runningDaily, setRunningDaily] = useState(false);
  const [toast, setToast] = useState("");

  const activeTemplate = templates.find((template) => template.slug === templateSlug) ?? report?.template ?? fallbackTemplate();

  const loadDaily = async (range = { start: startDate, end: endDate, template: templateSlug }) => {
    setLoading(true);
    try {
      const next = await api.daily({ start_date: range.start, end_date: range.end, template_slug: range.template });
      setReport(next);
      const selectedStillVisible = next.items.some((item) => item.id === selectedId);
      if (!selectedStillVisible) setSelectedId(next.items[0]?.id ?? null);
    } catch (error) {
      setToast(readError(error, "日报加载失败"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.templates()
      .then((items) => {
        setTemplates(items);
        if (items.length && !items.some((template) => template.slug === templateSlug)) {
          setTemplateSlug(DEFAULT_TEMPLATE_SLUG);
        }
      })
      .catch((error) => setToast(readError(error, "模板加载失败")));
  }, []);

  useEffect(() => {
    window.localStorage.setItem("tech-pr-template", templateSlug);
    loadDaily({ start: startDate, end: endDate, template: templateSlug });
  }, [startDate, endDate, templateSlug]);

  useEffect(() => {
    if (!selectedId) {
      setClip(null);
      return;
    }
    api.clipPayload(selectedId).then(setClip).catch(() => setClip(null));
  }, [selectedId]);

  useEffect(() => {
    const entries = Object.entries(jobIdsByVideo);
    if (!entries.length) return;
    const timer = window.setInterval(async () => {
      const completedVideos: number[] = [];
      const nextJobs: Record<number, Job> = {};
      await Promise.all(
        entries.map(async ([videoIdRaw, jobId]) => {
          const videoId = Number(videoIdRaw);
          try {
            const job = await api.job(jobId);
            nextJobs[job.id] = job;
            if (!PROCESSING_STATUSES.has(job.status)) completedVideos.push(videoId);
          } catch {
            completedVideos.push(videoId);
          }
        }),
      );
      if (Object.keys(nextJobs).length) setJobs((current) => ({ ...current, ...nextJobs }));
      if (completedVideos.length) {
        setJobIdsByVideo((current) => {
          const next = { ...current };
          completedVideos.forEach((videoId) => delete next[videoId]);
          return next;
        });
        await loadDaily({ start: startDate, end: endDate, template: templateSlug });
        if (selectedId) {
          api.clipPayload(selectedId).then(setClip).catch(() => undefined);
        }
      }
    }, 2200);
    return () => window.clearInterval(timer);
  }, [jobIdsByVideo, startDate, endDate, templateSlug, selectedId]);

  const filteredItems = useMemo(() => {
    const items = report?.items ?? [];
    const term = search.trim().toLowerCase();
    if (!term) return items;
    return items.filter((item) => {
      const haystack = `${item.title} ${item.summary} ${item.channel_title} ${item.matched_people} ${item.candidate_people}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [report, search]);

  const stats = useMemo(() => buildStats(report?.items ?? []), [report]);

  const runDaily = async () => {
    if (endDate < startDate) {
      setToast("结束日期不能早于开始日期。");
      return;
    }
    setRunningDaily(true);
    try {
      const next = await api.runDaily({ start_date: startDate, end_date: endDate, template_slug: activeTemplate.slug, limit_per_query: 3 });
      setReport(next);
      setToast(`${activeTemplate.name}抓取完成。`);
      if (next.items[0]) setSelectedId(next.items[0].id);
    } catch (error) {
      setToast(readError(error, "抓取失败"));
    } finally {
      setRunningDaily(false);
    }
  };

  const startDownloadTranslate = async (video: Video) => {
    setSelectedId(video.id);
    setToast("正在下载并翻译，完成后会出现在剪辑工作台。");
    try {
      const job = await api.downloadTranslate(video.id, { quality: "1080p" });
      setJobIdsByVideo((current) => ({ ...current, [video.id]: job.job_id }));
      setJobs((current) => ({
        ...current,
        [job.job_id]: {
          id: job.job_id,
          type: "download_translate",
          status: "queued",
          message: job.message,
          payload: JSON.stringify({ video_id: video.id }),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      }));
    } catch (error) {
      setToast(readError(error, "下载翻译失败"));
    }
  };

  const selectedVideo = (report?.items ?? []).find((item) => item.id === selectedId) ?? clip?.video ?? null;
  const activeJobId = selectedId ? jobIdsByVideo[selectedId] : undefined;
  const selectedProcessing = Boolean(activeJobId) || Boolean(selectedVideo && VIDEO_PROCESSING_STATUSES.has(selectedVideo.status));

  const selectVideo = (id: number, focusClip = false) => {
    setSelectedId(id);
    if (focusClip) {
      window.setTimeout(() => {
        document.getElementById("clip-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 60);
    }
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark">
            <GlobeHemisphereEast size={24} weight="duotone" />
          </div>
          <div>
            <h1>{activeTemplate.page_title}</h1>
            <p>{activeTemplate.description}</p>
          </div>
        </div>
        <div className="header-actions">
          <label className="template-control">
            <span>主题</span>
            <select value={activeTemplate.slug} onChange={(event) => setTemplateSlug(event.target.value)}>
              {templates.map((template) => (
                <option key={template.slug} value={template.slug}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
          <TemplateSettings
            activeTemplate={activeTemplate}
            onClone={async () => {
              const cloned = await api.cloneTemplate(activeTemplate.slug, { name: `${activeTemplate.name} 自定义` });
              setTemplates((current) => [...current.filter((item) => item.slug !== cloned.slug), cloned]);
              setTemplateSlug(cloned.slug);
              setToast("已复制为自定义模板，可以编辑关键词。");
            }}
            onSave={async (updates) => {
              const saved = await api.updateTemplate(activeTemplate.slug, updates);
              setTemplates((current) => current.map((item) => (item.slug === saved.slug ? saved : item)));
              setReport((current) => (current && current.template_slug === saved.slug ? { ...current, template: saved } : current));
              setToast("模板设置已保存。");
            }}
            onError={setToast}
          />
          <label className="date-control">
            <CalendarBlank size={17} />
            <span>开始</span>
            <input value={startDate} type="date" onInput={(event) => setStartDate(event.currentTarget.value)} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="date-control">
            <CalendarBlank size={17} />
            <span>结束</span>
            <input value={endDate} type="date" onInput={(event) => setEndDate(event.currentTarget.value)} onChange={(event) => setEndDate(event.target.value)} />
          </label>
          <button className="primary" onClick={runDaily} disabled={runningDaily}>
            {runningDaily ? <SpinnerGap size={17} className="spin" /> : <DownloadSimple size={17} />}
            {runningDaily ? "抓取中" : activeTemplate.run_button_label}
          </button>
        </div>
      </header>

      <section className="summary-strip">
        <Metric label="候选视频" value={stats.total} detail="按北京时间区间" />
        <Metric label="可处理" value={stats.ready} detail="可下载翻译" />
        <Metric label="处理中" value={stats.processing} detail="下载/字幕/转写" />
        <Metric label="可剪辑" value={stats.clipReady} detail="已带中文字幕" />
      </section>

      <section className="source-strip">
        {(report?.source_runs ?? []).map((source) => (
          <SourcePill key={`${source.name}-${source.status}`} source={source} />
        ))}
      </section>

      <section className="workbench-grid">
        <div className="daily-panel">
          <div className="panel-toolbar">
            <div>
              <h2>{startDate === endDate ? startDate : `${startDate} 至 ${endDate}`} {activeTemplate.list_title}</h2>
              <p>{report ? `北京时间窗口：${formatDate(report.window_start)} - ${formatDate(report.window_end)}` : "正在准备日报"}</p>
            </div>
            <label className="search-control">
              <MagnifyingGlass size={17} />
              <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={activeTemplate.search_placeholder} />
            </label>
          </div>
          {loading ? (
            <LoadingRows />
          ) : filteredItems.length ? (
            <InterviewList
              items={filteredItems}
              selectedId={selectedId}
              jobs={jobs}
              jobIdsByVideo={jobIdsByVideo}
              onSelect={selectVideo}
              onOpenClip={(video) => selectVideo(video.id, true)}
              onDownloadTranslate={startDownloadTranslate}
            />
          ) : (
            <EmptyState onRun={runDaily} running={runningDaily} template={activeTemplate} />
          )}
        </div>

        <aside className="status-panel">
          <TaskStatus selectedVideo={selectedVideo} jobs={jobs} activeJobId={activeJobId} />
        </aside>
      </section>

      <ClipWorkspace
        clip={clip}
        selectedVideo={selectedVideo}
        processing={selectedProcessing}
        template={activeTemplate}
        onDownloadTranslate={startDownloadTranslate}
        onRefresh={() => selectedId && api.clipPayload(selectedId).then(setClip)}
        onToast={setToast}
      />

      {toast && (
        <button className="toast" onClick={() => setToast("")}>
          {toast}
        </button>
      )}
    </main>
  );
}

function TemplateSettings({
  activeTemplate,
  onClone,
  onSave,
  onError,
}: {
  activeTemplate: TopicTemplate;
  onClone: () => Promise<void>;
  onSave: (updates: Partial<TopicTemplate>) => Promise<void>;
  onError: (message: string) => void;
}) {
  const [draft, setDraft] = useState(() => templateToDraft(activeTemplate));
  const [saving, setSaving] = useState(false);
  const custom = activeTemplate.is_builtin !== 1;

  useEffect(() => {
    setDraft(templateToDraft(activeTemplate));
  }, [activeTemplate.slug, activeTemplate.updated_at]);

  const save = async () => {
    if (!custom) return;
    setSaving(true);
    try {
      await onSave({
        name: draft.name.trim() || activeTemplate.name,
        page_title: draft.page_title.trim() || activeTemplate.page_title,
        description: draft.description.trim(),
        youtube_queries: linesToList(draft.youtube_queries),
        bilibili_queries: linesToList(draft.bilibili_queries),
        topic_terms: linesToList(draft.topic_terms),
        highlight_terms: linesToList(draft.highlight_terms),
      });
    } catch (error) {
      onError(readError(error, "模板保存失败"));
    } finally {
      setSaving(false);
    }
  };

  const clone = async () => {
    setSaving(true);
    try {
      await onClone();
    } catch (error) {
      onError(readError(error, "复制模板失败"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <details className="template-settings">
      <summary>
        模板设置
        <CaretDown size={14} />
      </summary>
      <div className="template-settings-popover">
        <div className="template-settings-head">
          <strong>{activeTemplate.name}</strong>
          <span>{custom ? "自定义模板" : "内置模板，复制后可编辑"}</span>
        </div>
        <label>
          名称
          <input
            readOnly={!custom}
            value={draft.name}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
        </label>
        <label>
          页面标题
          <input
            readOnly={!custom}
            value={draft.page_title}
            onChange={(event) => setDraft({ ...draft, page_title: event.target.value })}
          />
        </label>
        <label>
          说明
          <textarea
            readOnly={!custom}
            value={draft.description}
            onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          />
        </label>
        <div className="template-settings-grid">
          <label>
            YouTube 查询词
            <textarea
              readOnly={!custom}
              value={draft.youtube_queries}
              onChange={(event) => setDraft({ ...draft, youtube_queries: event.target.value })}
            />
          </label>
          <label>
            B站查询词
            <textarea
              readOnly={!custom}
              value={draft.bilibili_queries}
              onChange={(event) => setDraft({ ...draft, bilibili_queries: event.target.value })}
            />
          </label>
        </div>
        <div className="template-settings-grid">
          <label>
            相关词
            <textarea
              readOnly={!custom}
              value={draft.topic_terms}
              onChange={(event) => setDraft({ ...draft, topic_terms: event.target.value })}
            />
          </label>
          <label>
            高光词
            <textarea
              readOnly={!custom}
              value={draft.highlight_terms}
              onChange={(event) => setDraft({ ...draft, highlight_terms: event.target.value })}
            />
          </label>
        </div>
        <div className="template-settings-actions">
          <button type="button" onClick={clone} disabled={saving}>
            {saving && !custom ? <SpinnerGap size={15} className="spin" /> : <PlusCircle size={15} />}
            复制为自定义
          </button>
          <button className="primary" type="button" onClick={save} disabled={!custom || saving}>
            {saving && custom ? <SpinnerGap size={15} className="spin" /> : <CheckCircle size={15} />}
            保存模板
          </button>
        </div>
      </div>
    </details>
  );
}

function InterviewList(props: {
  items: Video[];
  selectedId: number | null;
  jobs: Record<number, Job>;
  jobIdsByVideo: Record<number, number>;
  onSelect: (id: number) => void;
  onOpenClip: (video: Video) => void;
  onDownloadTranslate: (video: Video) => void;
}) {
  return (
    <div className="interview-list">
      {props.items.map((video) => {
        const jobId = props.jobIdsByVideo[video.id];
        const job = jobId ? props.jobs[jobId] : undefined;
        const processing = Boolean(jobId) || VIDEO_PROCESSING_STATUSES.has(video.status);
        return (
          <article key={video.id} className={`interview-row ${props.selectedId === video.id ? "selected" : ""}`} onClick={() => props.onSelect(video.id)}>
            <Thumbnail className="thumb" url={video.thumbnail_url} />
            <div className="row-main">
              <div className="row-title-line">
                <h3>{video.title}</h3>
                <StatusBadge status={processing ? "running" : video.status} />
              </div>
              <VideoSummary summary={video.summary} />
              <div className="row-meta">
                <span>{platformLabel(video.platform)}</span>
                <span>{video.channel_title || "未知来源"}</span>
                <span>{formatDate(video.published_at)}</span>
                <span>{formatDuration(video.duration_seconds)}</span>
                <span>{formatNumber(video.view_count)} 次观看</span>
                <PeopleSignal video={video} />
              </div>
              {job?.message && <div className="inline-job">{job.message}</div>}
              {video.last_error && <div className="inline-error">{video.last_error}</div>}
            </div>
            <div className="row-actions" onClick={(event) => event.stopPropagation()}>
              <button className="ghost-action" onClick={() => props.onOpenClip(video)}>
                <Scissors size={16} />
                剪辑
              </button>
              <a href={video.url} target="_blank" rel="noreferrer">
                <ArrowSquareOut size={16} />
                原始链接
              </a>
              <button onClick={() => props.onDownloadTranslate(video)} disabled={processing}>
                {processing ? <SpinnerGap size={16} className="spin" /> : <DownloadSimple size={16} />}
                {video.status === "clip_ready" ? "重新下载翻译" : processing ? "处理中" : "下载并翻译"}
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function TaskStatus({ selectedVideo, jobs, activeJobId }: { selectedVideo: Video | null; jobs: Record<number, Job>; activeJobId?: number }) {
  const job = activeJobId ? jobs[activeJobId] : undefined;
  if (!selectedVideo) {
    return (
      <div className="status-empty">
        <Clock size={22} />
        <h2>等待选择视频</h2>
        <p>选择任意采访后，这里会显示下载翻译状态和下一步动作。</p>
      </div>
    );
  }
  const ready = selectedVideo.status === "clip_ready" || selectedVideo.status === "translated" || selectedVideo.status === "clipped" || selectedVideo.status === "exported";
  return (
    <div className="task-card">
      <div className="task-head">
        <StatusBadge status={job?.status ?? selectedVideo.status} />
        <span>{selectedVideo.source_tier === "experimental" ? "实验源" : "稳定源"}</span>
      </div>
      <h2>{selectedVideo.title}</h2>
      <p>{job?.message || selectedVideo.summary || "还没有任务。点击列表里的“下载并翻译”开始处理。"}</p>
      <div className="task-steps">
        <Step done={ready || selectedVideo.status !== "ready"} active={selectedVideo.status === "downloading"} label="下载视频" />
        <Step done={ready || selectedVideo.status === "subtitle_fetching" || selectedVideo.status === "translating"} active={selectedVideo.status === "subtitle_fetching"} label="拉取字幕" />
        <Step done={ready} active={selectedVideo.status === "transcribing" || selectedVideo.status === "translating"} label="转写翻译" />
        <Step done={ready} active={ready} label="进入剪辑" />
      </div>
      <a className="wide-link" href={selectedVideo.url} target="_blank" rel="noreferrer">
        <LinkSimple size={16} />
        打开原始视频
      </a>
    </div>
  );
}

function VideoSummary({ summary }: { summary: string }) {
  const fallback = "待生成摘要。点击抓取或下载翻译后会补全内容摘要。";
  const text = summary || fallback;
  const marker = text.match(/\s(可剪辑点：|关注点：)/);
  const markerIndex = marker?.index ?? -1;
  const main = markerIndex > 0 ? text.slice(0, markerIndex).trim() : text;
  const detail = markerIndex > 0 ? text.slice(markerIndex).trim() : "";
  return (
    <div className="video-summary">
      <p>{main}</p>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function PeopleSignal({ video }: { video: Video }) {
  const tracked = video.matched_people?.trim();
  const candidate = video.candidate_people?.trim();
  const reason = video.people_match_reason || "标题、简介和已有字幕未识别到明确人物";
  if (tracked) {
    return (
      <span className="person-chip tracked" title={reason}>
        追踪：{tracked}
      </span>
    );
  }
  if (candidate) {
    return (
      <span className="person-chip inferred" title={reason}>
        识别：{candidate}
      </span>
    );
  }
  return (
    <span className="person-chip unknown" title={reason}>
      人物待确认
    </span>
  );
}

function Thumbnail({ className, url }: { className: string; url: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className={className}>
      {url && !failed ? <img src={url} alt="" onError={() => setFailed(true)} /> : <FilmSlate size={28} />}
    </div>
  );
}

function ClipWorkspace({
  clip,
  selectedVideo,
  processing,
  template,
  onDownloadTranslate,
  onRefresh,
  onToast,
}: {
  clip: ClipPayload | null;
  selectedVideo: Video | null;
  processing: boolean;
  template: TopicTemplate;
  onDownloadTranslate: (video: Video) => void;
  onRefresh: () => void;
  onToast: (message: string) => void;
}) {
  const video = clip?.video ?? selectedVideo;
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const activeCaptionRef = useRef<HTMLButtonElement | null>(null);
  const [form, setForm] = useState({ start_seconds: "0", end_seconds: "15", label: "PR 短切片段", note: "", quote: "" });
  const [currentTime, setCurrentTime] = useState(0);
  const [mediaDuration, setMediaDuration] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [savingClip, setSavingClip] = useState(false);
  const [renderResult, setRenderResult] = useState<ClipRenderResult | null>(null);
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [exportOptions, setExportOptions] = useState({ destination: "downloads", output_dir: "", filename: "" });
  const zh = clip?.transcripts.filter((item) => item.language === "zh") ?? [];
  const en = clip?.transcripts.filter((item) => item.language === "en") ?? [];
  const rows = buildTranscriptRows(zh, en);
  const lastTranscriptEnd = rows.length ? rows[rows.length - 1].end : 0;
  const timelineDuration = Math.max(mediaDuration, video?.duration_seconds || 0, lastTranscriptEnd, Number(form.end_seconds) || 0, 1);
  const suggestions = useMemo(() => buildHighlightSuggestions(rows, timelineDuration, template), [rows, timelineDuration, template.slug, template.updated_at]);
  const activeTranscriptIndex = rows.findIndex((row) => currentTime >= row.start && currentTime < row.end);

  useEffect(() => {
    setForm({ start_seconds: "0", end_seconds: "15", label: "PR 短切片段", note: "", quote: "" });
    setCurrentTime(0);
    setMediaDuration(0);
    setRenderResult(null);
    setSavingClip(false);
    setExportDialogOpen(false);
    setExportOptions({ destination: "downloads", output_dir: "", filename: video?.title ? defaultExportFilename(video.title) : "" });
  }, [video?.id]);

  useEffect(() => {
    if (activeTranscriptIndex < 0) return;
    activeCaptionRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeTranscriptIndex]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const tracks = videoRef.current?.textTracks;
      if (!tracks?.length) return;
      for (let index = 0; index < tracks.length; index += 1) {
        tracks[index].mode = tracks[index].language === "zh-Hans" || index === 0 ? "showing" : "disabled";
      }
    }, 80);
    return () => window.clearTimeout(timer);
  }, [clip?.media_url, rows.length, video?.id]);

  if (!video) {
    return (
      <section id="clip-workspace" className="clip-workspace empty-clip-workspace">
        <div className="status-empty">
          <Scissors size={24} />
          <h2>还没有选择剪辑视频</h2>
          <p>从上方采访列表点击任意一条，或点击列表右侧“剪辑”按钮，这里会显示当前要处理的视频。</p>
        </div>
      </section>
    );
  }

  const ready = video.status === "clip_ready" || video.status === "translated" || video.status === "clipped" || video.status === "exported";
  const hasMedia = Boolean(clip?.media_url);
  const canEdit = ready && Boolean(clip);
  const clipMarks = clip?.clip_marks ?? [];

  const showChineseTextTrack = () => {
    const tracks = videoRef.current?.textTracks;
    if (!tracks?.length) return;
    for (let index = 0; index < tracks.length; index += 1) {
      tracks[index].mode = tracks[index].language === "zh-Hans" || index === 0 ? "showing" : "disabled";
    }
  };

  const seekTo = (seconds: number) => {
    const safe = clamp(seconds, 0, timelineDuration);
    setCurrentTime(safe);
    if (videoRef.current && Number.isFinite(videoRef.current.duration)) {
      videoRef.current.currentTime = safe;
    }
  };

  const applyRange = (start: number, end: number, label: string, note: string, quote = "") => {
    const safeStart = clamp(start, 0, timelineDuration);
    const safeEnd = clamp(Math.max(end, safeStart + 1), safeStart + 1, timelineDuration || safeStart + 1);
    setForm({
      start_seconds: toSecondInput(safeStart),
      end_seconds: toSecondInput(safeEnd),
      label,
      note,
      quote,
    });
    seekTo(safeStart);
  };

  const setPointFromPlayhead = (field: "start_seconds" | "end_seconds") => {
    const safe = toSecondInput(currentTime);
    if (field === "start_seconds") {
      const end = Math.max(Number(form.end_seconds) || 0, currentTime + 1);
      setForm({ ...form, start_seconds: safe, end_seconds: toSecondInput(end) });
      onToast("已设置入点。移动到结束位置后，点击“设为结束并加入序列”。");
      return;
    }
    setForm({ ...form, end_seconds: safe });
  };

  const nudgePlayhead = (offset: number) => {
    seekTo(currentTime + offset);
  };

  const saveClipRange = async (payload: { start: number; end: number; label: string; note: string; quote?: string; successMessage: string }) => {
    if (!clip || savingClip) return;
    const start = clamp(payload.start, 0, timelineDuration);
    const end = clamp(payload.end, start, timelineDuration || payload.end);
    if (end <= start) {
      onToast("出点必须晚于入点。");
      return;
    }
    const duplicate = clipMarks.some((mark) => Math.abs(mark.start_seconds - start) < 0.5 && Math.abs(mark.end_seconds - end) < 0.5);
    if (duplicate) {
      onToast("这段已经在剪辑序列里了。");
      return;
    }
    setSavingClip(true);
    try {
      await api.createClip({
        video_id: clip.video.id,
        start_seconds: start,
        end_seconds: end,
        label: payload.label,
        note: payload.note,
        quote: payload.quote ?? "",
        status: "ready",
      });
      onToast(payload.successMessage);
      onRefresh();
    } catch (error) {
      onToast(readError(error, "加入剪辑序列失败"));
    } finally {
      setSavingClip(false);
    }
  };

  const submitClip = async (event: FormEvent) => {
    event.preventDefault();
    await saveClipRange({
      start: Number(form.start_seconds),
      end: Number(form.end_seconds),
      label: form.label || "手动片段",
      note: form.note,
      quote: form.quote,
      successMessage: "已保存手动片段。",
    });
  };

  const finishSelectionAtPlayhead = async () => {
    const start = Number(form.start_seconds);
    const end = currentTime;
    if (end <= start) {
      onToast("请先移动到晚于入点的位置，再加入剪辑序列。");
      return;
    }
    setForm({ ...form, end_seconds: toSecondInput(end) });
    await saveClipRange({
      start,
      end,
      label: form.label || "手动片段",
      note: form.note || `手动选区 ${formatTimecode(start)} - ${formatTimecode(end)}`,
      quote: form.quote,
      successMessage: "已加入剪辑序列。",
    });
  };

  const addSuggestionToSequence = async (suggestion: HighlightSuggestion) => {
    seekTo(suggestion.start);
    await saveClipRange({
      start: suggestion.start,
      end: suggestion.end,
      label: suggestion.label,
      note: suggestion.reason,
      quote: suggestion.quote,
      successMessage: "已把推荐高光加入剪辑序列。",
    });
  };

  const removeFromSequence = async (clipMarkId: number) => {
    try {
      const result = await api.deleteClip(clipMarkId);
      onToast(result.message);
      onRefresh();
    } catch (error) {
      onToast(readError(error, "移除片段失败"));
    }
  };

  const renderSavedClips = async () => {
    if (!video || !clipMarks.length) return;
    if (exportOptions.destination === "custom" && !exportOptions.output_dir.trim()) {
      onToast("请填写自定义保存文件夹路径。");
      return;
    }
    setRendering(true);
    try {
      const result = await api.renderClips(video.id, exportOptions);
      setRenderResult(result);
      onToast(result.message);
      setExportDialogOpen(false);
      onRefresh();
    } catch (error) {
      onToast(readError(error, "导出片段视频失败"));
    } finally {
      setRendering(false);
    }
  };

  return (
    <section id="clip-workspace" className="clip-workspace">
      <div className="clip-heading">
        <div>
          <h2>剪辑工作台</h2>
          <p>{ready ? (hasMedia ? "当前视频、中文字幕和打点工具已就绪。" : "已有字幕，但还缺少本地视频文件。") : "下载翻译完成后，这里会出现播放器、字幕和剪辑打点。"}</p>
        </div>
        <div className="export-actions">
          <details className="secondary-export-menu">
            <summary>
              更多导出
              <CaretDown size={14} />
            </summary>
            <div className="secondary-export-list">
              <a className={!ready ? "disabled" : ""} href={ready ? `/api/videos/${video.id}/export?format=vtt&language=zh` : undefined}>
                <Subtitles size={16} />
                字幕 VTT
              </a>
              <a className={!ready ? "disabled" : ""} href={ready ? `/api/videos/${video.id}/export?format=srt&language=zh` : undefined}>
                <FileArrowDown size={16} />
                字幕 SRT
              </a>
              <a className={!clipMarks.length ? "disabled" : ""} href={clipMarks.length ? `/api/videos/${video.id}/export?format=csv` : undefined}>
                <Scissors size={16} />
                剪辑表 CSV
              </a>
            </div>
          </details>
          <button className="primary export-primary" onClick={() => setExportDialogOpen(true)} disabled={!hasMedia || !clipMarks.length || rendering}>
            {rendering ? <SpinnerGap size={16} className="spin" /> : <FileArrowDown size={16} />}
            {rendering ? "导出中" : "导出序列视频..."}
          </button>
        </div>
      </div>

      <div className="active-video-card">
        <Thumbnail className="active-thumb" url={video.thumbnail_url} />
        <div className="active-video-main">
          <div className="active-video-title">
            <span>当前剪辑视频</span>
            <StatusBadge status={processing ? "running" : video.status} />
          </div>
          <h3>{video.title}</h3>
          <div className="row-meta compact">
            <span>{platformLabel(video.platform)}</span>
            <span>{video.channel_title || "未知来源"}</span>
            <span>{formatDate(video.published_at)}</span>
            <span>{formatDuration(video.duration_seconds)}</span>
            <span>{rows.length ? `${rows.length} 条字幕` : "暂无字幕"}</span>
            <span>{hasMedia ? "本地视频已就绪" : "未下载本地视频"}</span>
          </div>
        </div>
        <div className="active-video-actions">
          <a href={video.url} target="_blank" rel="noreferrer">
            <ArrowSquareOut size={16} />
            原始链接
          </a>
          <button onClick={() => onDownloadTranslate(video)} disabled={processing}>
            {processing ? <SpinnerGap size={16} className="spin" /> : <DownloadSimple size={16} />}
            {hasMedia ? "重新下载" : "下载视频"}
          </button>
        </div>
      </div>

      <div className="clip-grid">
        <div className="player-panel">
          {clip?.media_url ? (
            <>
              <video
                controls
                ref={videoRef}
                src={clip.media_url}
                onLoadedMetadata={(event) => {
                  setMediaDuration(event.currentTarget.duration || 0);
                  setCurrentTime(event.currentTarget.currentTime || 0);
                  window.setTimeout(showChineseTextTrack, 0);
                }}
                onSeeked={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
                onSeeking={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime || 0)}
              >
                {ready && zh.length > 0 && (
                  <track
                    default
                    kind="subtitles"
                    label="中文字幕"
                    src={`/api/videos/${video.id}/export?format=vtt&language=zh&disposition=inline`}
                    srcLang="zh-Hans"
                  />
                )}
              </video>
              <ClipTimeline
                currentTime={currentTime}
                duration={timelineDuration}
                marks={clipMarks}
                suggestions={suggestions}
                selectionStart={Number(form.start_seconds)}
                selectionEnd={Number(form.end_seconds)}
                onSeek={seekTo}
                onPreviewSuggestion={(suggestion) => seekTo(suggestion.start)}
              />
              <div className="transport-panel">
                <div>
                  <span>当前播放</span>
                  <strong>
                    {formatTimecode(currentTime)} / {formatTimecode(timelineDuration)}
                  </strong>
                </div>
                <div className="transport-actions">
                  <button type="button" onClick={() => nudgePlayhead(-5)}>
                    -5 秒
                  </button>
                  <button type="button" onClick={() => nudgePlayhead(5)}>
                    +5 秒
                  </button>
                  <button className="wide-action" type="button" onClick={() => setPointFromPlayhead("start_seconds")}>
                    设为开始
                  </button>
                  <button className="primary wide-action" type="button" onClick={finishSelectionAtPlayhead} disabled={!canEdit || savingClip}>
                    {savingClip ? "加入中" : "设为结束并加入序列"}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="video-placeholder">
              <PlayCircle size={34} />
              <strong>{ready ? "缺少本地视频文件" : "等待本地视频"}</strong>
              <span>{ready ? "这条视频已有字幕，但还没有下载到本地，无法在工作台内预览画面。" : "点击“下载并翻译”后，完成的视频会在这里播放。"}</span>
              <div className="placeholder-actions">
                <button className="primary" onClick={() => onDownloadTranslate(video)} disabled={processing}>
                  {processing ? <SpinnerGap size={16} className="spin" /> : <DownloadSimple size={16} />}
                  {processing ? "处理中" : "下载视频"}
                </button>
                <a href={video.url} target="_blank" rel="noreferrer">
                  打开原始链接
                </a>
              </div>
            </div>
          )}
          <HighlightPanel suggestions={suggestions} onAdd={addSuggestionToSequence} onSeek={seekTo} saving={savingClip} />
          <div className="manual-clip-panel">
            <div className="manual-clip-head">
              <div>
                <h3>手动片段</h3>
                <p>需要精确改秒数时使用；推荐高光可以直接加入序列。</p>
              </div>
              <strong>
                {formatTimecode(Number(form.start_seconds))} - {formatTimecode(Number(form.end_seconds))}
              </strong>
            </div>
            <form className="manual-clip-form" onSubmit={submitClip}>
              <label>
                入点
                <input value={form.start_seconds} onChange={(event) => setForm({ ...form, start_seconds: event.target.value })} inputMode="decimal" />
              </label>
              <label>
                出点
                <input value={form.end_seconds} onChange={(event) => setForm({ ...form, end_seconds: event.target.value })} inputMode="decimal" />
              </label>
              <label className="span-2">
                标签
                <input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} />
              </label>
              <label className="span-2">
                备注
                <textarea value={form.note} onChange={(event) => setForm({ ...form, note: event.target.value })} />
              </label>
              <button className="primary span-2" disabled={!canEdit || savingClip}>
                {savingClip ? <SpinnerGap size={16} className="spin" /> : <PlusCircle size={16} />}
                {canEdit ? "加入剪辑序列" : "等待字幕就绪"}
              </button>
            </form>
          </div>
          <ExportResult result={renderResult} />
        </div>

        <div className="transcript-panel">
          <div className="transcript-head">
            <h3>双语字幕</h3>
            <span>{rows.length ? `${rows.length} 段` : "等待生成"}</span>
          </div>
          <div className="transcript-list">
            {rows.length ? (
              rows.map((row, index) => (
                <button
                  className={`transcript-row ${index === activeTranscriptIndex ? "active" : ""}`}
                  key={`${row.start}-${index}`}
                  onClick={() => applyRange(row.start, row.end, "字幕选区", "从字幕行加入剪辑序列", row.zh?.text || row.en?.text || "")}
                  ref={index === activeTranscriptIndex ? (node) => {
                    activeCaptionRef.current = node;
                  } : undefined}
                >
                  <span className="timecode">{formatTimecode(row.start)}</span>
                  <span>
                    <strong>{row.zh?.text || "暂无中文字幕"}</strong>
                    {row.en?.text && <small>{row.en.text}</small>}
                  </span>
                </button>
              ))
            ) : (
              <div className="transcript-empty">点击“下载并翻译”后，中文字幕会在这里逐段显示。</div>
            )}
          </div>
        </div>

        <ClipSequence marks={clipMarks} onDelete={removeFromSequence} onSeek={seekTo} />
      </div>
      {exportDialogOpen && (
        <div className="export-modal-backdrop" role="presentation">
          <div className="export-modal" role="dialog" aria-modal="true" aria-label="导出序列视频">
            <div className="export-modal-head">
              <div>
                <h3>导出序列视频</h3>
                <p>选择最终 MP4 的保存位置。系统会同时保留工作台内的预览文件。</p>
              </div>
              <button className="ghost-action" type="button" onClick={() => setExportDialogOpen(false)} disabled={rendering}>
                取消
              </button>
            </div>
            <div className="export-save-grid">
              <button
                className={`export-save-choice ${exportOptions.destination === "downloads" ? "active" : ""}`}
                type="button"
                onClick={() => setExportOptions({ ...exportOptions, destination: "downloads" })}
              >
                下载文件夹
                <span>~/Downloads/Tech PR Clips</span>
              </button>
              <button
                className={`export-save-choice ${exportOptions.destination === "desktop" ? "active" : ""}`}
                type="button"
                onClick={() => setExportOptions({ ...exportOptions, destination: "desktop" })}
              >
                桌面
                <span>~/Desktop/Tech PR Clips</span>
              </button>
              <button
                className={`export-save-choice ${exportOptions.destination === "custom" ? "active" : ""}`}
                type="button"
                onClick={() => setExportOptions({ ...exportOptions, destination: "custom" })}
              >
                自定义路径
                <span>例如 ~/Movies/PR Clips</span>
              </button>
            </div>
            {exportOptions.destination === "custom" && (
              <label className="export-field">
                保存文件夹路径
                <input
                  value={exportOptions.output_dir}
                  onChange={(event) => setExportOptions({ ...exportOptions, output_dir: event.target.value })}
                  placeholder="~/Movies/PR Clips"
                />
              </label>
            )}
            <label className="export-field">
              文件名
              <input
                value={exportOptions.filename}
                onChange={(event) => setExportOptions({ ...exportOptions, filename: event.target.value })}
                placeholder={video ? defaultExportFilename(video.title) : "clip-sequence.mp4"}
              />
            </label>
            <div className="export-modal-actions">
              <button type="button" onClick={() => setExportDialogOpen(false)} disabled={rendering}>
                取消
              </button>
              <button className="primary" type="button" onClick={renderSavedClips} disabled={rendering}>
                {rendering ? <SpinnerGap size={16} className="spin" /> : <FileArrowDown size={16} />}
                {rendering ? "导出中" : "导出并保存"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ClipTimeline({
  currentTime,
  duration,
  marks,
  suggestions,
  selectionStart,
  selectionEnd,
  onSeek,
  onPreviewSuggestion,
}: {
  currentTime: number;
  duration: number;
  marks: ClipMark[];
  suggestions: HighlightSuggestion[];
  selectionStart: number;
  selectionEnd: number;
  onSeek: (seconds: number) => void;
  onPreviewSuggestion: (suggestion: HighlightSuggestion) => void;
}) {
  const safeDuration = Math.max(duration, 1);
  const progress = (clamp(currentTime, 0, safeDuration) / safeDuration) * 100;
  const safeSelectionStart = clamp(Number.isFinite(selectionStart) ? selectionStart : 0, 0, safeDuration);
  const safeSelectionEnd = clamp(Number.isFinite(selectionEnd) ? selectionEnd : 0, 0, safeDuration);
  const selectionDuplicatesMark = marks.some((mark) => Math.abs(mark.start_seconds - safeSelectionStart) < 0.5 && Math.abs(mark.end_seconds - safeSelectionEnd) < 0.5);
  const hasSelection = safeSelectionEnd > safeSelectionStart && !selectionDuplicatesMark;
  const suggestionBands = buildTimelineBands(
    suggestions.map((suggestion, index) => ({
      key: suggestion.id,
      start: suggestion.start,
      end: suggestion.end,
      label: `高光${index + 1}`,
      title: `${suggestion.label} · ${formatTimecode(suggestion.start)} - ${formatTimecode(suggestion.end)}`,
      action: () => onPreviewSuggestion(suggestion),
    })),
    safeDuration,
  );
  const clipBands = buildTimelineBands(
    marks.map((mark, index) => ({
      key: String(mark.id),
      start: mark.start_seconds,
      end: mark.end_seconds,
      label: `剪辑${index + 1}`,
      title: `${mark.label || `剪辑${index + 1}`} · ${formatTimecode(mark.start_seconds)} - ${formatTimecode(mark.end_seconds)}`,
      action: () => onSeek(mark.start_seconds),
    })),
    safeDuration,
  );
  const laneHeight = 42;
  const topPadding = 24;
  const rowGap = 10;
  const suggestionTop = topPadding;
  const suggestionLaneCount = Math.max(1, suggestionBands.laneCount);
  const clipTop = suggestionTop + suggestionLaneCount * laneHeight + rowGap;
  const clipLaneCount = Math.max(1, clipBands.laneCount);
  const selectionTop = clipTop + clipLaneCount * laneHeight + rowGap;
  const stageHeight = selectionTop + (hasSelection ? laneHeight : 14) + topPadding;
  const selectionLeft = (safeSelectionStart / safeDuration) * 100;
  const selectionWidth = ((safeSelectionEnd - safeSelectionStart) / safeDuration) * 100;
  return (
    <div className="timeline-panel">
      <div className="timeline-head">
        <span>剪辑时间线</span>
        <strong>{hasSelection ? `当前选区 ${formatTimecode(safeSelectionStart)} - ${formatTimecode(safeSelectionEnd)}` : `${marks.length} 段剪辑 · ${suggestions.length} 个高光`}</strong>
      </div>
      <div className="timeline-track-wrap compact">
        <div className="timeline-stage" style={{ minHeight: `${stageHeight}px` }}>
          <span className="timeline-row-label" style={{ top: `${suggestionTop + 4}px` }}>
            高光建议
          </span>
          <span className="timeline-row-label" style={{ top: `${clipTop + 4}px` }}>
            剪辑序列
          </span>
          {suggestionBands.items.map((band) => (
            <button
              className="timeline-segment suggestion-segment"
              key={band.key}
              style={timelineBandStyle(band, suggestionTop + band.lane * laneHeight)}
              title={band.title}
              type="button"
              onClick={band.action}
            >
              <span>{band.label}</span>
            </button>
          ))}
          {clipBands.items.map((band) => (
            <button
              className="timeline-segment clip-segment"
              key={band.key}
              style={timelineBandStyle(band, clipTop + band.lane * laneHeight)}
              title={band.title}
              type="button"
              onClick={band.action}
            >
              <span>{band.label}</span>
            </button>
          ))}
          {!marks.length && <span className="timeline-empty-row" style={{ top: `${clipTop + 2}px` }}>还没有加入剪辑序列</span>}
          {hasSelection && (
            <button
              className="timeline-segment selection-segment"
              style={timelineBandStyle({ left: selectionLeft, width: selectionWidth }, selectionTop)}
              title={`当前选区 ${formatTimecode(safeSelectionStart)} - ${formatTimecode(safeSelectionEnd)}`}
              type="button"
              onClick={() => onSeek(safeSelectionStart)}
            >
              <span>当前选区</span>
            </button>
          )}
          <span className="timeline-playhead" style={{ "--left": progress / 100 } as CSSProperties} />
        </div>
        <input
          aria-label="拖动视频时间线"
          className="timeline-range"
          max={safeDuration}
          min={0}
          step={0.1}
          type="range"
          value={clamp(currentTime, 0, safeDuration)}
          onChange={(event) => onSeek(Number(event.currentTarget.value))}
        />
      </div>
      <div className="timeline-legend">
        <span>高光建议</span>
        <span>剪辑序列</span>
        <span>当前选区</span>
      </div>
    </div>
  );
}

function HighlightPanel({ suggestions, onAdd, onSeek, saving }: { suggestions: HighlightSuggestion[]; onAdd: (suggestion: HighlightSuggestion) => void; onSeek: (seconds: number) => void; saving: boolean }) {
  return (
    <div className="highlight-panel">
      <div className="transcript-head">
        <h3>推荐高光</h3>
        <span>{suggestions.length ? "一键加入剪辑序列" : "等待字幕"}</span>
      </div>
      {suggestions.length ? (
        <div className="highlight-list">
          {suggestions.map((suggestion) => (
            <article className="highlight-card" key={suggestion.id}>
              <div className="highlight-meta">
                <span>
                  {formatTimecode(suggestion.start)} - {formatTimecode(suggestion.end)}
                </span>
                <strong>{suggestion.label}</strong>
              </div>
              <p>{suggestion.quote || suggestion.reason}</p>
              <div className="highlight-actions">
                <button type="button" onClick={() => onSeek(suggestion.start)}>
                  预览
                </button>
                <button className="primary" type="button" onClick={() => onAdd(suggestion)} disabled={saving}>
                  {saving ? "保存中" : "加入序列"}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="transcript-empty">下载翻译后，会根据字幕关键词、观点密度和时间跨度自动推荐高光。</div>
      )}
    </div>
  );
}

function ExportResult({ result }: { result: ClipRenderResult | null }) {
  if (!result) return null;
  return (
    <div className="export-result">
      <div>
        <strong>序列视频已导出</strong>
        <span>{result.message}</span>
      </div>
      {result.saved_path && (
        <div className="saved-path">
          <span>最终 MP4 保存到</span>
          <code>{result.saved_path}</code>
        </div>
      )}
      <div className="saved-path secondary">
        <span>工作台预览缓存</span>
        <code>{result.export_dir}</code>
      </div>
      {result.sequence_url && (
        <a className="sequence-link" href={result.sequence_url} target="_blank" rel="noreferrer">
          打开合成序列视频
        </a>
      )}
      <div className="exported-clips">
        {result.clips.map((clip) => (
          <a href={clip.url} key={clip.path} target="_blank" rel="noreferrer">
            {clip.label || "片段"} · {formatTimecode(clip.start_seconds)}
          </a>
        ))}
      </div>
    </div>
  );
}

function ClipSequence({ marks, onDelete, onSeek }: { marks: ClipMark[]; onDelete: (id: number) => void; onSeek: (seconds: number) => void }) {
  const totalSeconds = marks.reduce((sum, mark) => sum + Math.max(mark.end_seconds - mark.start_seconds, 0), 0);
  return (
    <div className="marks-panel">
      <div className="transcript-head">
        <h3>剪辑序列</h3>
        <span>{marks.length ? `${marks.length} 段 · ${formatDuration(totalSeconds)}` : "空序列"}</span>
      </div>
      {marks.length ? (
        <>
          <div className="sequence-strip" aria-label="剪辑序列缩略时间线">
            {marks.map((mark) => (
              <button key={mark.id} style={{ flexGrow: Math.max(mark.end_seconds - mark.start_seconds, 2) }} type="button" onClick={() => onSeek(mark.start_seconds)}>
                {formatTimecode(mark.start_seconds)}
              </button>
            ))}
          </div>
          {marks.map((mark, index) => (
            <div className="mark-row" key={mark.id}>
              <span>
                #{index + 1} · {formatTimecode(mark.start_seconds)} - {formatTimecode(mark.end_seconds)}
              </span>
              <strong>{mark.label}</strong>
              <p>{mark.note || mark.quote || "无备注"}</p>
              <div className="sequence-actions">
                <button type="button" onClick={() => onSeek(mark.start_seconds)}>
                  跳到源片段
                </button>
                <button className="ghost-action" type="button" onClick={() => onDelete(mark.id)}>
                  <Trash size={14} />
                  移除
                </button>
              </div>
            </div>
          ))}
        </>
      ) : (
        <div className="transcript-empty">还没有片段。像剪辑软件一样先设入点/出点，或从推荐高光一键加入。</div>
      )}
    </div>
  );
}

function SourcePill({ source }: { source: SourceRun }) {
  const experimental = source.tier === "experimental" || source.status === "planned" || source.status === "manual";
  return (
    <div className={`source-pill ${experimental ? "experimental" : ""}`}>
      {experimental ? <WarningCircle size={16} /> : <CheckCircle size={16} />}
      <strong>{source.name}</strong>
      <span>{source.message}</span>
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const kind = status === "failed" ? "bad" : status === "clip_ready" || status === "completed" || status === "translated" ? "good" : status === "running" || status === "queued" ? "busy" : "";
  return <span className={`status-badge ${kind}`}>{status === "running" || status === "queued" ? "处理中" : statusLabel(status)}</span>;
}

function Step({ done, active, label }: { done: boolean; active: boolean; label: string }) {
  return (
    <div className={`step ${done ? "done" : ""} ${active ? "active" : ""}`}>
      <span>{done ? <CheckCircle size={14} weight="fill" /> : active ? <SpinnerGap size={14} className="spin" /> : <Clock size={14} />}</span>
      {label}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="loading-rows">
      {Array.from({ length: 5 }).map((_, index) => (
        <div className="skeleton-row" key={index}>
          <span />
          <div>
            <i />
            <i />
            <i />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmptyState({ onRun, running, template }: { onRun: () => void; running: boolean; template: TopicTemplate }) {
  return (
    <div className="empty-state">
      <FilmSlate size={36} />
      <h2>{template.empty_title}</h2>
      <p>{template.empty_description}</p>
      <button className="primary" onClick={onRun} disabled={running}>
        {running ? <SpinnerGap size={17} className="spin" /> : <DownloadSimple size={17} />}
        {running ? "抓取中" : template.run_button_label}
      </button>
    </div>
  );
}

interface TimelineBandSource {
  key: string;
  start: number;
  end: number;
  label: string;
  title: string;
  action: () => void;
}

interface TimelineBand extends TimelineBandSource {
  lane: number;
  left: number;
  width: number;
}

function buildTimelineBands(sources: TimelineBandSource[], duration: number): { items: TimelineBand[]; laneCount: number } {
  const safeDuration = Math.max(duration, 1);
  const laneEnds: number[] = [];
  const items = sources
    .map((source, order) => {
      const start = clamp(source.start, 0, safeDuration);
      const end = clamp(Math.max(source.end, start + 0.1), start + 0.1, safeDuration);
      return { ...source, start, end, order };
    })
    .filter((source) => source.end > source.start)
    .sort((a, b) => a.start - b.start || a.end - b.end || a.order - b.order)
    .map((source) => {
      let lane = laneEnds.findIndex((laneEnd) => source.start >= laneEnd + 0.35);
      if (lane < 0) {
        lane = laneEnds.length;
        laneEnds.push(source.end);
      } else {
        laneEnds[lane] = source.end;
      }
      const left = (source.start / safeDuration) * 100;
      const right = (source.end / safeDuration) * 100;
      return {
        ...source,
        lane,
        left,
        width: Math.max(right - left, 0.55),
      };
    });
  return { items, laneCount: Math.max(laneEnds.length, 0) };
}

function timelineBandStyle(band: Pick<TimelineBand, "left" | "width">, top: number): CSSProperties {
  return {
    "--left": band.left / 100,
    "--width": band.width / 100,
    top: `${top}px`,
  } as CSSProperties;
}

function buildStats(items: Video[]) {
  return {
    total: items.length,
    ready: items.filter((item) => item.status === "ready" || item.status === "new" || item.status === "shortlisted").length,
    processing: items.filter((item) => VIDEO_PROCESSING_STATUSES.has(item.status)).length,
    clipReady: items.filter((item) => item.status === "clip_ready" || item.status === "translated" || item.status === "clipped" || item.status === "exported").length,
  };
}

function defaultExportFilename(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, " ").trim().slice(0, 48) || "clip-sequence";
  return `${cleaned}-剪辑序列.mp4`;
}

function buildTranscriptRows(zh: Transcript[], en: Transcript[]) {
  const source = zh.length ? zh : en;
  return source.map((item, index) => ({
    start: item.start_seconds,
    end: item.end_seconds,
    zh: zh[index],
    en: en[index],
  }));
}

function buildHighlightSuggestions(rows: TranscriptRow[], duration: number, template: TopicTemplate): HighlightSuggestion[] {
  if (!rows.length) return [];
  const scored = rows
    .map((row, index) => {
      const text = `${row.zh?.text ?? ""} ${row.en?.text ?? ""}`.trim();
      const score = scoreHighlightText(text, template.highlight_terms);
      return { row, index, text, score };
    })
    .filter((item) => item.score > 0 && item.text.length > 10)
    .sort((a, b) => b.score - a.score || a.row.start - b.row.start);

  const selected: HighlightSuggestion[] = [];
  for (const item of scored) {
    if (selected.length >= 6) break;
    const start = clamp(item.row.start - 4, 0, duration);
    const nextRows = rows.slice(item.index, item.index + 8);
    const nextEnd = nextRows.length ? nextRows[nextRows.length - 1].end : item.row.end;
    const end = clamp(Math.max(nextEnd + 5, start + 18), start + 1, Math.min(duration, start + 90));
    if (selected.some((suggestion) => Math.abs(suggestion.start - start) < 18)) continue;
    selected.push({
      id: `highlight-${item.index}-${Math.round(item.row.start)}`,
      start,
      end,
      label: highlightLabel(item.text),
      reason: `系统根据字幕中的${template.name}高光词、观点密度和可传播表达自动推荐。`,
      quote: trimText(item.text, 120),
      score: item.score,
    });
  }

  if (selected.length) return selected.sort((a, b) => a.start - b.start);

  const fallbackRows = rows.filter((row) => row.end - row.start >= 3).slice(0, 4);
  return fallbackRows.map((row, index) => ({
    id: `fallback-${index}-${Math.round(row.start)}`,
    start: clamp(row.start, 0, duration),
    end: clamp(Math.max(row.end, row.start + 18), row.start + 1, duration),
    label: "待复核片段",
    reason: "字幕可用但缺少强关键词，先按早期内容给出候选。",
    quote: trimText(row.zh?.text || row.en?.text || "", 120),
    score: 1,
  }));
}

function scoreHighlightText(text: string, extraTerms: string[] = []): number {
  const normalized = text.toLowerCase();
  const terms = [
    "agent",
    "agi",
    "openai",
    "deepseek",
    "nvidia",
    "model",
    "startup",
    "product",
    "safety",
    "regulation",
    "future",
    "i think",
    "why",
    "because",
    "智能体",
    "大模型",
    "开源",
    "商业化",
    "监管",
    "风险",
    "创业",
    "产品",
    "算力",
    "未来",
    "我认为",
    "为什么",
    "关键",
    "机会",
    "趋势",
    ...extraTerms,
  ];
  let score = 0;
  for (const term of terms) {
    if (normalized.includes(term)) score += term.length > 4 ? 2 : 1;
  }
  if (/[?？]/.test(text)) score += 1;
  if (text.length >= 38 && text.length <= 180) score += 1;
  return score;
}

function highlightLabel(text: string): string {
  const normalized = text.toLowerCase();
  if (normalized.includes("demo") || text.includes("演示")) return "产品演示";
  if (normalized.includes("launch") || normalized.includes("release") || text.includes("发布")) return "发布重点";
  if (normalized.includes("pricing") || text.includes("价格")) return "价格信号";
  if (normalized.includes("customer") || text.includes("客户")) return "客户案例";
  if (normalized.includes("agent") || text.includes("智能体")) return "Agent 观点";
  if (normalized.includes("agi") || text.includes("通用人工智能")) return "AGI 判断";
  if (normalized.includes("safety") || text.includes("安全") || text.includes("风险")) return "安全与风险";
  if (normalized.includes("startup") || text.includes("创业") || text.includes("商业化")) return "商业化观点";
  if (text.includes("未来") || text.includes("趋势") || normalized.includes("future")) return "趋势判断";
  return "观点高光";
}

function trimText(value: string, max: number): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length > max ? `${compact.slice(0, max)}...` : compact;
}

function toSecondInput(seconds: number): string {
  return String(Math.round(Math.max(seconds, 0) * 10) / 10);
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function templateToDraft(template: TopicTemplate) {
  return {
    name: template.name,
    page_title: template.page_title,
    description: template.description,
    youtube_queries: listToLines(template.youtube_queries),
    bilibili_queries: listToLines(template.bilibili_queries),
    topic_terms: listToLines(template.topic_terms),
    highlight_terms: listToLines(template.highlight_terms),
  };
}

function listToLines(values: string[]) {
  return (values || []).join("\n");
}

function linesToList(value: string) {
  return value
    .split(/\n|,|，/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function fallbackTemplate(): TopicTemplate {
  const timestamp = new Date().toISOString();
  return {
    slug: DEFAULT_TEMPLATE_SLUG,
    name: "AI 采访",
    page_title: "AI 采访日报",
    description: "按日期区间追踪 AI 圈新增采访，保留原链，一键下载翻译后进入剪辑。",
    list_title: "AI 采访列表",
    run_button_label: "抓取区间 AI 采访",
    empty_title: "还没有这个区间的真实采访候选",
    empty_description: "点击抓取后，系统会按人物名单、AI 采访关键词和重点 B站账号搜索，并按真实发布时间过滤。",
    search_placeholder: "搜人物、标题、频道",
    summary_focus: "AI/科技趋势",
    compliance_note: "自动发现只保存元数据和原始链接；下载剪辑前请确认素材授权。",
    youtube_queries: ["AI interview", "artificial intelligence interview", "AI conversation"],
    bilibili_queries: ["AI 采访", "人工智能 访谈", "大模型 访谈"],
    topic_terms: ["ai", "artificial intelligence", "llm", "人工智能", "大模型"],
    scoring_terms: {},
    highlight_terms: ["agent", "model", "product", "智能体", "大模型", "产品"],
    is_builtin: 1,
    base_slug: "",
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function defaultBeijingRange() {
  const now = new Date();
  const beijing = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  beijing.setUTCDate(beijing.getUTCDate() - 1);
  const end = beijing.toISOString().slice(0, 10);
  return { start: end, end };
}

function readError(error: unknown, fallback: string) {
  if (error instanceof Error) return error.message;
  return fallback;
}

function platformLabel(platform: string) {
  if (platform === "youtube") return "YouTube";
  if (platform === "bilibili") return "B站";
  return platform;
}

export default App;
