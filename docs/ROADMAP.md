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

2. **Local runtime architecture** — Planned
   - Move long-running work to a persistent SQLite-backed worker.
   - Restore queued/running jobs after browser or service restarts.
   - Add retryable progress states and one-command local startup.

3. **Publish-ready rough cuts** — Planned
   - Add 16:9 and 9:16 output profiles.
   - Add basic crop/fill controls, subtitle templates, and logo overlay.
   - Validate output dimensions and subtitle placement before rendering.

4. **Focused web workflow** — Planned
   - Separate discovery, task status, and the clip editor into focused views.
   - Restore the selected item and editing context after refresh.
   - Reduce duplicate actions and optimize long transcript rendering.

5. **Release verification** — Planned
   - Cover real discovery/download, restart recovery, and video export.
   - Add browser smoke tests and clean-machine setup verification.
   - Finish troubleshooting and user documentation for the v1 release.
