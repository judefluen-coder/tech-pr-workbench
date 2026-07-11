export interface ClipDeliveryAsset {
  kind: string;
  url: string;
}

export interface ClipDeliveryMark {
  end_seconds: number;
  label: string;
  note: string;
  quote: string;
  start_seconds: number;
  status: string;
}

export interface ClipDeliveryRenderResult {
  clip_status_filter: string;
  clips: unknown[];
  rendered_duration_seconds: number;
  sequence_url: string;
}

export interface ClipDeliveryVideo {
  channel_title: string;
  platform: string;
  published_at: string;
  title: string;
  url: string;
}

export interface ClipDeliverySummary {
  approvedCount: number;
  exportedUrls: string[];
  isReady: boolean;
  marksCount: number;
  missingCopyCount: number;
  pendingItems: string[];
  sequenceDuration: number;
  statusLabel: string;
  unapprovedCount: number;
}

export type ClipDeliveryNextStepId = "copy" | "copy-brief" | "export" | "review" | "sequence" | "view-copy";

export interface ClipDeliveryNextStep {
  id: ClipDeliveryNextStepId;
  label: string;
}

export interface ClipDeliveryHandoffPrompt {
  label: string;
  message: string;
  tone: "pending" | "ready";
}

export function buildClipDeliverySummary({
  assets,
  marks,
  origin,
  renderResult,
}: {
  assets: ClipDeliveryAsset[];
  marks: ClipDeliveryMark[];
  origin: string;
  renderResult: ClipDeliveryRenderResult | null;
}): ClipDeliverySummary {
  const exportedUrls = exportedSequenceAssets(assets, renderResult, origin).map((asset) => asset.url);
  const approvedCount = marks.filter((mark) => mark.status === "approved").length;
  const missingCopyCount = marks.filter((mark) => clipDeliveryCopyGaps(mark).length).length;
  const unapprovedCount = marks.length - approvedCount;
  const pendingItems = deliveryPendingItems({
    exported: exportedUrls.length > 0,
    marksCount: marks.length,
    missingCopyCount,
    unapprovedCount,
  });
  return {
    approvedCount,
    exportedUrls,
    isReady: pendingItems.length === 0,
    marksCount: marks.length,
    missingCopyCount,
    pendingItems,
    sequenceDuration: clipMarksDuration(marks),
    statusLabel: pendingItems.length ? `待处理 · ${pendingItems.join(" · ")}` : "可交付",
    unapprovedCount,
  };
}

export function buildClipDeliveryBrief({
  assets,
  marks,
  origin,
  renderResult,
  video,
}: {
  assets: ClipDeliveryAsset[];
  marks: ClipDeliveryMark[];
  origin: string;
  renderResult: ClipDeliveryRenderResult | null;
  video: ClipDeliveryVideo;
}): string {
  const summary = buildClipDeliverySummary({ assets, marks, origin, renderResult });
  const sourceParts = [platformLabel(video.platform), video.channel_title || "未知来源", formatDeliveryDate(video.published_at)].filter(Boolean);
  const lines = [
    `# ${video.title || "未命名视频"}`,
    `来源：${sourceParts.join(" · ")}`,
    `原始链接：${video.url || "待确认"}`,
    `剪辑序列：${summary.marksCount} 段 · ${formatDeliveryDuration(summary.sequenceDuration)}`,
    `审片状态：${summary.approvedCount}/${summary.marksCount} 已确认`,
    `交付状态：${summary.statusLabel}`,
    `最近导出：${renderResult ? `${renderResult.clip_status_filter === "approved" ? "仅已确认" : "全部序列"} · ${renderResult.clips.length} 段 · 实际 ${formatDeliveryDuration(renderResult.rendered_duration_seconds)}` : "待导出"}`,
    `成片 MP4：${summary.exportedUrls.length ? summary.exportedUrls.join("；") : "待导出"}`,
    "",
    "## 片段顺序",
  ];
  if (!marks.length) {
    lines.push("暂无剪辑片段。");
  } else {
    marks.forEach((mark, index) => {
      const duration = Math.max(mark.end_seconds - mark.start_seconds, 0);
      const copyGaps = clipDeliveryCopyGaps(mark);
      const copyNote = copyGaps.length ? `，缺文案：${copyGaps.join("、")}` : "";
      lines.push(`${index + 1}. ${mark.label || "未命名片段"}（${formatDeliveryTimecode(mark.start_seconds)} - ${formatDeliveryTimecode(mark.end_seconds)}，${formatDeliveryDuration(duration)}，${clipStatusLabel(mark.status)}${copyNote}）`);
      const note = cleanBriefLine(mark.quote || mark.note);
      if (note) lines.push(`   ${mark.quote ? "引用" : "备注"}：${truncateBriefText(note, 180)}`);
    });
  }
  return lines.join("\n");
}

export function clipDeliveryCopyGaps(mark: Pick<ClipDeliveryMark, "label" | "note" | "quote">): string[] {
  const gaps: string[] = [];
  if (!hasUsefulClipLabel(mark.label)) gaps.push("标题");
  if (!mark.note.trim()) gaps.push("备注");
  if (!mark.quote.trim()) gaps.push("引用");
  return gaps;
}

export function buildClipDeliveryNextStep(summary: ClipDeliverySummary, options: { canAutofillCopy?: boolean } = {}): ClipDeliveryNextStep {
  if (!summary.marksCount) return { id: "sequence", label: "搭建序列" };
  if (summary.missingCopyCount) return options.canAutofillCopy ? { id: "copy", label: "补齐文案" } : { id: "view-copy", label: "查看缺文案" };
  if (summary.unapprovedCount) return { id: "review", label: "继续审片" };
  if (!summary.exportedUrls.length) return { id: "export", label: "导出成片" };
  return { id: "copy-brief", label: "复制交付稿" };
}

export function buildClipDeliveryHandoffPrompt(summary: ClipDeliverySummary): ClipDeliveryHandoffPrompt {
  if (summary.isReady) {
    return {
      label: "复制交付稿",
      message: `${summary.marksCount} 段已确认，成片已导出。`,
      tone: "ready",
    };
  }
  return {
    label: "复制状态稿",
    message: summary.pendingItems.join(" · ") || "等待交付信息更新。",
    tone: "pending",
  };
}

function deliveryPendingItems({
  exported,
  marksCount,
  missingCopyCount,
  unapprovedCount,
}: {
  exported: boolean;
  marksCount: number;
  missingCopyCount: number;
  unapprovedCount: number;
}): string[] {
  const pending: string[] = [];
  if (!marksCount) pending.push("待搭建序列");
  if (unapprovedCount) pending.push(`${unapprovedCount} 段待确认`);
  if (missingCopyCount) pending.push(`${missingCopyCount} 段缺文案`);
  if (!exported) pending.push("待导出成片");
  return pending;
}

function exportedSequenceAssets(assets: ClipDeliveryAsset[], renderResult: ClipDeliveryRenderResult | null, origin: string) {
  const exported = assets
    .filter((asset) => asset.kind === "exported_sequence" && asset.url)
    .map((asset) => ({
      url: absoluteUrl(asset.url, origin),
    }));
  if (renderResult?.sequence_url) {
    exported.unshift({
      url: absoluteUrl(renderResult.sequence_url, origin),
    });
  }
  const seen = new Set<string>();
  return exported.filter((asset) => {
    if (seen.has(asset.url)) return false;
    seen.add(asset.url);
    return true;
  });
}

function clipMarksDuration(marks: ClipDeliveryMark[]): number {
  return marks.reduce((sum, mark) => sum + Math.max(mark.end_seconds - mark.start_seconds, 0), 0);
}

function hasUsefulClipLabel(label: string): boolean {
  const cleanLabel = label.trim();
  return Boolean(cleanLabel) && cleanLabel !== "未命名片段";
}

function clipStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    approved: "已确认",
    draft: "待审",
    ready: "可用",
  };
  return labels[status] ?? (status || "待审");
}

function platformLabel(platform: string): string {
  if (platform === "youtube") return "YouTube";
  if (platform === "bilibili") return "B站";
  return platform;
}

function absoluteUrl(url: string, origin: string): string {
  if (!url) return "";
  if (/^https?:\/\//.test(url)) return url;
  const prefix = origin.replace(/\/$/, "");
  return `${prefix}${url.startsWith("/") ? "" : "/"}${url}`;
}

function cleanBriefLine(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function truncateBriefText(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(limit - 3, 0)).trim()}...`;
}

function formatDeliveryDate(value: string): string {
  if (!value) return "待确认";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(date);
}

function formatDeliveryDuration(seconds: number): string {
  const safe = Number.isFinite(seconds) ? seconds : 0;
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = Math.floor(safe % 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function formatDeliveryTimecode(seconds: number): string {
  const safe = Math.max(seconds || 0, 0);
  const minutes = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}
