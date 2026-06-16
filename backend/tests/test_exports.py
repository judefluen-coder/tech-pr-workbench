from app.exports import clip_marks_to_csv, segments_to_srt, segments_to_vtt


def test_segments_to_srt_and_vtt() -> None:
    segments = [{"start_seconds": 0, "end_seconds": 3.5, "text": "你好"}, {"start_seconds": 3.5, "end_seconds": 8, "text": "第二句"}]
    srt = segments_to_srt(segments)
    vtt = segments_to_vtt(segments)
    assert "00:00:00,000 --> 00:00:03,500" in srt
    assert srt.startswith("1\n")
    assert vtt.startswith("WEBVTT")
    assert "00:00:03.500 --> 00:00:08.000" in vtt


def test_clip_marks_to_csv() -> None:
    csv_text = clip_marks_to_csv(
        [
            {
                "start_seconds": 10,
                "end_seconds": 22.2,
                "label": "金句",
                "note": "适合短切",
                "quote": "AI is a tool",
                "status": "ready",
            }
        ]
    )
    assert "start,end,label,note,quote,status" in csv_text
    assert "金句" in csv_text
    assert "00:00:22,200" in csv_text

