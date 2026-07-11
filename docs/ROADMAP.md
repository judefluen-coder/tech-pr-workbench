# Local Studio v1 Roadmap

## Goal

Turn Tech PR Workbench into a reliable single-user local web studio: discover and download authorized YouTube/Bilibili interviews, produce clean bilingual subtitles and rough-cut suggestions, refine clips in the browser, and export branded 16:9 or 9:16 videos.

## Scope

- Local single-user web application.
- Native full-feature startup for browser-assisted OpenCLI discovery.
- Reproducible Docker Compose deployment for the web app, API, and worker.
- Persistent local database, media, subtitle, and export directories.
- Human-reviewed rough cuts rather than fully automatic publishing.

Authentication, billing, real-time collaboration, multi-track editing, complex transitions, and automatic social publishing are outside the v1 scope.

## Stages

1. **Stable baseline** — Complete
   - Clean YouTube rolling captions and malformed HTML entities.
   - Reprocess existing subtitles without downloading the video again.
   - Preserve clip order, review state, and video workflow status.
   - Verify the current clip review, preflight, export, and delivery workflow.

2. **Local runtime architecture** — Complete
   - Moved download, subtitle reprocessing, and rendering to a persistent SQLite-backed worker.
   - Restore interrupted worker jobs after service restarts and hydrate active jobs after browser refresh.
   - Added progress, retry, duplicate-job protection, one-command native startup, and Docker Compose configuration.

3. **Publish-ready rough cuts** — Complete
   - Added source, 1920×1080 landscape, and 1080×1920 portrait output profiles.
   - Added crop/contain framing, horizontal subject focus, subtitle templates and safe zones, and uploaded Logo overlays.
   - Validate all render options before queuing and verify output dimensions, burned subtitles, and Logo pixels in integration tests.

4. **Focused web workflow** — Complete
   - Separated discovery, persistent task history, and the clip editor into focused views.
   - Restore the date range, selected video, active view, playhead, draft clip form, transcript search, and export settings after refresh.
   - Added task-to-video context and retry actions, plus progressive long-transcript rendering that keeps the active caption available.
   - Verified desktop and mobile layouts, including internal task scrolling and export-modal overflow behavior.

5. **Release verification** — Planned
   - Cover real discovery/download, restart recovery, and video export.
   - Add browser smoke tests and clean-machine setup verification.
   - Finish troubleshooting and user documentation for the v1 release.
