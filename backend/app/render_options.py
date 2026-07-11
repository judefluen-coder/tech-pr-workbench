from __future__ import annotations

OUTPUT_PROFILES = {
    "source": None,
    "landscape": (1920, 1080),
    "portrait": (1080, 1920),
}
FIT_MODES = {"crop", "contain"}
SUBTITLE_STYLES = {"standard", "bold", "minimal", "none"}
SUBTITLE_POSITIONS = {"bottom", "lower_third"}
LOGO_POSITIONS = {"top_left", "top_right", "bottom_left", "bottom_right"}


def normalize_render_options(options: dict) -> dict:
    output_profile = _choice(options.get("output_profile"), OUTPUT_PROFILES, "输出规格")
    fit_mode = _choice(options.get("fit_mode"), FIT_MODES, "画面适配")
    subtitle_style = _choice(options.get("subtitle_style"), SUBTITLE_STYLES, "字幕模板")
    subtitle_position = _choice(options.get("subtitle_position"), SUBTITLE_POSITIONS, "字幕位置")
    logo_position = _choice(options.get("logo_position"), LOGO_POSITIONS, "Logo 位置")
    try:
        focus_x = float(options.get("focus_x", 50))
    except (TypeError, ValueError) as exc:
        raise ValueError("主体位置必须是 0 到 100 之间的数字。") from exc
    if not 0 <= focus_x <= 100:
        raise ValueError("主体位置必须在 0 到 100 之间。")
    raw_logo_asset_id = options.get("logo_asset_id")
    logo_asset_id = None
    if raw_logo_asset_id not in {None, "", 0, "0"}:
        try:
            logo_asset_id = int(raw_logo_asset_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("Logo 素材编号无效。") from exc
        if logo_asset_id <= 0:
            raise ValueError("Logo 素材编号无效。")
    return {
        "output_profile": output_profile,
        "fit_mode": fit_mode,
        "focus_x": focus_x,
        "subtitle_style": subtitle_style,
        "subtitle_position": subtitle_position,
        "logo_asset_id": logo_asset_id,
        "logo_position": logo_position,
    }


def output_dimensions(output_profile: str, source_width: int, source_height: int) -> tuple[int, int]:
    dimensions = OUTPUT_PROFILES[output_profile]
    if dimensions:
        return dimensions
    return _even(source_width), _even(source_height)


def video_frame_filter(output_profile: str, fit_mode: str, focus_x: float) -> str:
    dimensions = OUTPUT_PROFILES[output_profile]
    if not dimensions:
        return ""
    width, height = dimensions
    if fit_mode == "contain":
        return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
    focus_ratio = round(focus_x / 100, 4)
    return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(in_w-out_w)*{focus_ratio}:(in_h-out_h)/2,setsar=1"


def subtitle_force_style(width: int, height: int, subtitle_style: str, subtitle_position: str) -> str:
    base_font_size = max(28, round(min(width, height) / 26))
    font_size = round(base_font_size * (1.14 if subtitle_style == "bold" else 0.96 if subtitle_style == "minimal" else 1))
    margin = subtitle_margin(height, subtitle_position)
    shared = f"FontName=Noto Sans CJK SC,FontSize={font_size},PrimaryColour=&H00FFFFFF,Alignment=2,MarginV={margin},Shadow=0"
    if subtitle_style == "bold":
        return f"{shared},Bold=1,BackColour=&H78000000,OutlineColour=&H00101010,BorderStyle=4,Outline=2"
    if subtitle_style == "minimal":
        return f"{shared},Bold=0,OutlineColour=&H00101010,BorderStyle=1,Outline=2"
    return f"{shared},Bold=0,BackColour=&H90000000,OutlineColour=&H00101010,BorderStyle=4,Outline=1"


def subtitle_margin(height: int, subtitle_position: str) -> int:
    ratio = 0.24 if subtitle_position == "lower_third" else 0.08
    return max(36, round(height * ratio))


def logo_overlay_position(logo_position: str, margin: int) -> tuple[str, str]:
    x = str(margin) if logo_position.endswith("left") else f"W-w-{margin}"
    y = str(margin) if logo_position.startswith("top") else f"H-h-{margin}"
    return x, y


def _choice(value: object, choices: object, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in choices:
        raise ValueError(f"无效{label}：{normalized or '空值'}。")
    return normalized


def _even(value: int) -> int:
    safe = max(int(value), 2)
    return safe if safe % 2 == 0 else safe - 1
