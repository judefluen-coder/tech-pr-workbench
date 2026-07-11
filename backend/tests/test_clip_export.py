from pathlib import Path

from app.clip_export import _clip_subtitle_segments, _copy_sequence_to_destination, _escape_filter_path, _filter_export_marks, _plan_export_marks


def test_clip_subtitle_segments_are_clamped_to_clip_time() -> None:
    transcripts = [
        {"start_seconds": 8, "end_seconds": 12, "text": "前半句"},
        {"start_seconds": 12, "end_seconds": 16, "text": "完整句"},
        {"start_seconds": 16, "end_seconds": 22, "text": "后半句"},
        {"start_seconds": 24, "end_seconds": 26, "text": "不在片段内"},
    ]

    segments = _clip_subtitle_segments(transcripts, 10, 20)

    assert segments == [
        {"start_seconds": 0, "end_seconds": 2, "text": "前半句"},
        {"start_seconds": 2, "end_seconds": 6, "text": "完整句"},
        {"start_seconds": 6, "end_seconds": 10, "text": "后半句"},
    ]


def test_escape_filter_path_escapes_ffmpeg_filter_delimiters() -> None:
    assert _escape_filter_path(Path("/tmp/a:b'srt")) == "/tmp/a\\:b\\'srt"


def test_plan_export_marks_trims_to_target_duration() -> None:
    marks = [
        {"id": 1, "start_seconds": 10, "end_seconds": 30, "label": "first"},
        {"id": 2, "start_seconds": 60, "end_seconds": 95, "label": "second"},
        {"id": 3, "start_seconds": 120, "end_seconds": 140, "label": "third"},
    ]

    planned = _plan_export_marks(marks, 30)

    assert [mark["id"] for mark in planned] == [1, 2]
    assert planned[0]["start_seconds"] == 10
    assert planned[0]["end_seconds"] == 30
    assert planned[1]["start_seconds"] == 60
    assert planned[1]["end_seconds"] == 70


def test_plan_export_marks_keeps_full_sequence_without_target_duration() -> None:
    marks = [{"id": 1, "start_seconds": 0, "end_seconds": 5}]
    assert _plan_export_marks(marks, 0) == marks


def test_filter_export_marks_can_keep_only_approved_clips() -> None:
    marks = [
        {"id": 1, "status": "draft"},
        {"id": 2, "status": "approved"},
        {"id": 3, "status": "ready"},
    ]

    assert [mark["id"] for mark in _filter_export_marks(marks, "approved")] == [2]
    assert [mark["id"] for mark in _filter_export_marks(marks, "all")] == [1, 2, 3]


def test_copy_sequence_to_custom_destination_dedupes_filename(tmp_path: Path) -> None:
    source = tmp_path / "sequence.mp4"
    source.write_bytes(b"video")
    target_dir = tmp_path / "exports"

    first = _copy_sequence_to_destination(source, 1, "A/B Test", "custom", target_dir, "final:name.mp4")
    second = _copy_sequence_to_destination(source, 1, "A/B Test", "custom", target_dir, "final:name.mp4")

    assert first.name == "final-name.mp4"
    assert second.name == "final-name-2.mp4"
    assert first.read_bytes() == b"video"
