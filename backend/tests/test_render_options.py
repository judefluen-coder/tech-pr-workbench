import pytest

from app.render_options import logo_overlay_position, normalize_render_options, output_dimensions, subtitle_force_style, subtitle_margin, video_frame_filter


def test_render_options_normalize_publish_profiles() -> None:
    assert normalize_render_options(
        {
            "output_profile": "portrait",
            "fit_mode": "crop",
            "focus_x": 72,
            "subtitle_style": "bold",
            "subtitle_position": "lower_third",
            "logo_asset_id": "9",
            "logo_position": "top_left",
        }
    ) == {
        "output_profile": "portrait",
        "fit_mode": "crop",
        "focus_x": 72.0,
        "subtitle_style": "bold",
        "subtitle_position": "lower_third",
        "logo_asset_id": 9,
        "logo_position": "top_left",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("output_profile", "square"),
        ("fit_mode", "stretch"),
        ("focus_x", 101),
        ("subtitle_style", "neon"),
        ("subtitle_position", "outside"),
        ("logo_position", "center"),
    ],
)
def test_render_options_reject_invalid_values(field: str, value: object) -> None:
    options = {
        "output_profile": "landscape",
        "fit_mode": "contain",
        "focus_x": 50,
        "subtitle_style": "standard",
        "subtitle_position": "bottom",
        "logo_position": "top_right",
    }
    options[field] = value
    with pytest.raises(ValueError):
        normalize_render_options(options)


def test_output_dimensions_and_frame_filters_are_stable() -> None:
    assert output_dimensions("landscape", 853, 479) == (1920, 1080)
    assert output_dimensions("portrait", 853, 479) == (1080, 1920)
    assert output_dimensions("source", 853, 479) == (852, 478)
    assert "crop=1080:1920:(in_w-out_w)*0.72" in video_frame_filter("portrait", "crop", 72)
    assert "pad=1920:1080:(ow-iw)/2:(oh-ih)/2" in video_frame_filter("landscape", "contain", 50)
    assert video_frame_filter("source", "crop", 50) == ""


def test_subtitle_templates_use_safe_output_relative_positions() -> None:
    assert subtitle_margin(1920, "bottom") == 154
    assert subtitle_margin(1920, "lower_third") == 461
    bold = subtitle_force_style(1080, 1920, "bold", "lower_third")
    minimal = subtitle_force_style(1920, 1080, "minimal", "bottom")
    assert "Bold=1" in bold and "MarginV=461" in bold
    assert "BorderStyle=1" in minimal and "MarginV=86" in minimal
    assert logo_overlay_position("top_right", 38) == ("W-w-38", "38")
    assert logo_overlay_position("bottom_left", 38) == ("38", "H-h-38")
