from app.ai import normalize_transcript_segments, parse_transcript_text


def test_youtube_rolling_vtt_is_collapsed_and_html_is_cleaned() -> None:
    text = """WEBVTT

00:00:05.000 --> 00:00:08.000 align:start position:0%

Welcome<00:00:06.000><c> &amp;</c><00:00:07.000><c> Startup DNA</c>

00:00:08.000 --> 00:00:08.010 align:start position:0%
Welcome &amp; Startup DNA

00:00:08.010 --> 00:00:11.000 align:start position:0%
Welcome &amp; Startup DNA
where<00:00:09.000><c> we</c><00:00:10.000><c> work</c>

00:00:11.000 --> 00:00:11.010 align:start position:0%
where we work

00:00:11.010 --> 00:00:14.000 align:start position:0%
where we work
&gt;&gt; Thanks<00:00:12.000><c> for</c><00:00:13.000><c> joining</c>
"""

    assert parse_transcript_text(text) == [
        {"start_seconds": 5, "end_seconds": 8, "text": "Welcome & Startup DNA"},
        {"start_seconds": 8.01, "end_seconds": 11, "text": "where we work"},
        {"start_seconds": 11.01, "end_seconds": 14, "text": "Thanks for joining"},
    ]


def test_regular_repeated_srt_captions_are_preserved() -> None:
    text = """1
00:00:00,000 --> 00:00:02,000
<i>Again &amp; again</i>

2
00:00:02,000 --> 00:00:04,000
Again &amp; again
"""

    assert parse_transcript_text(text) == [
        {"start_seconds": 0, "end_seconds": 2, "text": "Again & again"},
        {"start_seconds": 2, "end_seconds": 4, "text": "Again & again"},
    ]


def test_stored_transcript_entities_and_rolling_rows_are_normalized() -> None:
    segments = [
        {"start_seconds": 0, "end_seconds": 2, "text": "Hello &amp; welcome"},
        {"start_seconds": 2, "end_seconds": 2.01, "text": "Hello & amp; welcome"},
        {"start_seconds": 2.01, "end_seconds": 4, "text": "Hello &amp; welcome & gt; & gt; Back again"},
    ]

    assert normalize_transcript_segments(segments) == [
        {"start_seconds": 0, "end_seconds": 2, "text": "Hello & welcome"},
        {"start_seconds": 2.01, "end_seconds": 4, "text": "Back again"},
    ]
