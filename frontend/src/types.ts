export type VideoStatus =
  | "new"
  | "shortlisted"
  | "imported"
  | "translated"
  | "clipped"
  | "exported"
  | "archived"
  | "discovered"
  | "summarizing"
  | "ready"
  | "downloading"
  | "subtitle_fetching"
  | "transcribing"
  | "translating"
  | "clip_ready"
  | "failed";

export interface DashboardData {
  date: string;
  status_counts: Record<string, number>;
  top_videos: Video[];
  latest_job: Job | null;
  clip_count: number;
  people_count: number;
  compliance_note: string;
}

export interface Job {
  id: number;
  type: string;
  status: string;
  message: string;
  payload: string;
  created_at: string;
  updated_at: string;
}

export interface SourceRun {
  name: string;
  tier: "stable" | "experimental" | string;
  status: string;
  message: string;
}

export interface DailyReport {
  date: string;
  start_date: string;
  end_date: string;
  timezone: string;
  window_start: string;
  window_end: string;
  items: Video[];
  source_runs: SourceRun[];
  latest_job: Job | null;
  job_id?: number;
  run_result?: Record<string, unknown>;
}

export interface Person {
  id: number;
  name: string;
  english_name: string;
  aliases: string;
  priority: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface Video {
  id: number;
  platform: string;
  external_id: string;
  url: string;
  title: string;
  description: string;
  channel_title: string;
  published_at: string;
  duration_seconds: number;
  view_count: number;
  like_count: number;
  thumbnail_url: string;
  matched_people: string;
  candidate_people: string;
  people_match_reason: string;
  interview_confidence: number;
  priority_score: number;
  status: VideoStatus;
  compliance_note: string;
  summary: string;
  source_tier: string;
  last_error: string;
  created_at: string;
  updated_at: string;
}

export interface Transcript {
  id: number;
  video_id: number;
  language: "en" | "zh";
  start_seconds: number;
  end_seconds: number;
  text: string;
  source: string;
  created_at: string;
}

export interface ClipMark {
  id: number;
  video_id: number;
  start_seconds: number;
  end_seconds: number;
  label: string;
  note: string;
  quote: string;
  position: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MediaAsset {
  id: number;
  kind: string;
  original_filename: string;
  stored_path: string;
  authorization_note: string;
  delete_after_processing: number;
  processing_status: string;
  created_at: string;
  url: string;
}

export interface VideoDetail {
  video: Video;
  transcripts: Transcript[];
  clip_marks: ClipMark[];
  media_assets: MediaAsset[];
}

export interface ClipPayload extends VideoDetail {
  media_url: string;
}

export interface RenderedClip {
  id: number;
  label: string;
  start_seconds: number;
  end_seconds: number;
  path: string;
  url: string;
}

export interface ClipRenderResult {
  message: string;
  export_dir: string;
  sequence_path: string;
  sequence_url: string;
  saved_path: string;
  target_duration_seconds: number;
  clip_status_filter: string;
  rendered_duration_seconds: number;
  clips: RenderedClip[];
}

export interface SystemCheck {
  ok: boolean;
  label: string;
  message: string;
}

export type SystemStatus = Record<string, SystemCheck>;

export interface AutomationResult {
  ok: boolean;
  actions: Array<{ step: string; status: string; video_id?: number; message: string }>;
}
