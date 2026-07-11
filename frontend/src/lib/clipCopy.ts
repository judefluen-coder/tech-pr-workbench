export interface TranscriptCopySource {
  end: number;
  label: string;
  quote: string;
  start: number;
}

export interface TranscriptSnapRow {
  end: number;
  start: number;
  text: string;
}

export interface TranscriptClipCopy {
  label: string;
  note: string;
  quote: string;
}

export interface ClipCopyFields {
  label: string;
  note: string;
  quote: string;
}

export function buildTranscriptSnapForRange(rows: TranscriptSnapRow[], start: number, end: number): TranscriptCopySource | null {
  if (!rows.length || !Number.isFinite(start) || !Number.isFinite(end)) return null;
  const overlappingRows = rows.filter((row) => row.end > start && row.start < end);
  const snapRows = overlappingRows.length
    ? overlappingRows
    : [
        rows.reduce((nearest, row) => {
          const nearestDistance = Math.abs(nearest.start - start);
          const rowDistance = Math.abs(row.start - start);
          return rowDistance < nearestDistance ? row : nearest;
        }, rows[0]),
      ];
  const first = snapRows[0];
  const last = snapRows[snapRows.length - 1];
  const quote = snapRows.map((row) => row.text).filter(Boolean).join(" ");
  return {
    end: last.end,
    label: snapRows.length > 1 ? `${snapRows.length} 句字幕` : "1 句字幕",
    quote,
    start: first.start,
  };
}

export function buildTranscriptClipCopy(source: TranscriptCopySource | null | undefined): TranscriptClipCopy | null {
  const cleanQuote = source?.quote.replace(/\s+/g, " ").trim() ?? "";
  if (!source || !cleanQuote) return null;
  return {
    label: cleanQuote.length > 24 ? `${cleanQuote.slice(0, 24)}...` : cleanQuote,
    note: `字幕选区 ${formatTimecode(source.start)} - ${formatTimecode(source.end)} · ${source.label}`,
    quote: source.quote,
  };
}

export function hasUsefulClipLabel(label: string): boolean {
  const cleanLabel = label.trim();
  return Boolean(cleanLabel) && cleanLabel !== "未命名片段";
}

export function isClipCopyIncomplete(fields: ClipCopyFields): boolean {
  return !hasUsefulClipLabel(fields.label) || !fields.note.trim() || !fields.quote.trim();
}

export function mergeMissingClipCopyFields(fields: ClipCopyFields, copy: TranscriptClipCopy | null | undefined): TranscriptClipCopy | null {
  if (!copy || !isClipCopyIncomplete(fields)) return null;
  return {
    label: hasUsefulClipLabel(fields.label) ? fields.label : copy.label,
    note: fields.note.trim() ? fields.note : copy.note,
    quote: fields.quote.trim() ? fields.quote : copy.quote,
  };
}

export function clipCopyGapLabels(fields: ClipCopyFields): string[] {
  const labels: string[] = [];
  if (!hasUsefulClipLabel(fields.label)) labels.push("标题");
  if (!fields.note.trim()) labels.push("备注");
  if (!fields.quote.trim()) labels.push("引用");
  return labels;
}

function formatTimecode(seconds: number): string {
  const safe = Math.max(seconds || 0, 0);
  const minutes = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}
