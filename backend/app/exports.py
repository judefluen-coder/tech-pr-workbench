from __future__ import annotations

import csv
import io


def format_timestamp(seconds: float, sep: str = ",") -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02}:{minutes:02}:{secs:02}{sep}{millis:03}"


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        text = segment.get("text", "").strip()
        blocks.append(
            f"{index}\n"
            f"{format_timestamp(float(segment['start_seconds']))} --> {format_timestamp(float(segment['end_seconds']))}\n"
            f"{text}"
        )
    return "\n\n".join(blocks) + "\n"


def segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(
            f"{format_timestamp(float(segment['start_seconds']), '.')} --> "
            f"{format_timestamp(float(segment['end_seconds']), '.')}"
        )
        lines.append(segment.get("text", "").strip())
        lines.append("")
    return "\n".join(lines)


def clip_marks_to_csv(clip_marks: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["start", "end", "label", "note", "quote", "status"],
    )
    writer.writeheader()
    for mark in clip_marks:
        writer.writerow(
            {
                "start": format_timestamp(float(mark["start_seconds"])),
                "end": format_timestamp(float(mark["end_seconds"])),
                "label": mark["label"],
                "note": mark.get("note", ""),
                "quote": mark.get("quote", ""),
                "status": mark.get("status", "draft"),
            }
        )
    return output.getvalue()

