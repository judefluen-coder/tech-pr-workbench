from __future__ import annotations

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    template_slug: str = "ai-interviews"
    name: str
    english_name: str = ""
    aliases: str = ""
    priority: int = Field(default=3, ge=1, le=5)
    notes: str = ""


class VideoUpdate(BaseModel):
    status: str | None = None


class ClipMarkCreate(BaseModel):
    video_id: int
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    label: str
    note: str = ""
    quote: str = ""
    status: str = "draft"


class YoutubeSyncRequest(BaseModel):
    days_back: int = Field(default=1, ge=1, le=30)
    limit_per_query: int = Field(default=8, ge=1, le=25)
    include_demo_when_unconfigured: bool = True
    template_slug: str = "ai-interviews"


class DailyRunRequest(BaseModel):
    date: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    template_slug: str = "ai-interviews"
    limit_per_query: int = Field(default=5, ge=1, le=12)


class TemplateCloneRequest(BaseModel):
    name: str = ""
    slug: str = ""


class TemplateUpdateRequest(BaseModel):
    name: str | None = None
    page_title: str | None = None
    description: str | None = None
    list_title: str | None = None
    run_button_label: str | None = None
    empty_title: str | None = None
    empty_description: str | None = None
    search_placeholder: str | None = None
    summary_focus: str | None = None
    compliance_note: str | None = None
    youtube_queries: list[str] | None = None
    bilibili_queries: list[str] | None = None
    topic_terms: list[str] | None = None
    scoring_terms: dict[str, float] | None = None
    highlight_terms: list[str] | None = None


class DownloadRequest(BaseModel):
    authorization_note: str
    quality: str = Field(default="1080p")
    include_subtitles: bool = True
    include_thumbnail: bool = True


class DownloadTranslateRequest(BaseModel):
    authorization_note: str = ""
    quality: str = Field(default="1080p")


class RenderClipsRequest(BaseModel):
    destination: str = Field(default="downloads")
    output_dir: str = ""
    filename: str = ""


class AutomationRequest(BaseModel):
    days_back: int = Field(default=1, ge=1, le=30)
    limit_per_query: int = Field(default=4, ge=1, le=10)
    shortlist_threshold: float = Field(default=55, ge=0, le=100)
    auto_download: bool = False
    authorization_note: str = ""
    auto_transcribe: bool = False
