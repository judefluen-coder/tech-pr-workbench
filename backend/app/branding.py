from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.db import get_connection, now_iso, row_to_dict
from app.workflow import media_asset_with_url

ALLOWED_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 10 * 1024 * 1024


async def import_brand_logo(video_id: int, upload: UploadFile) -> dict:
    filename = upload.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_LOGO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Logo 只支持 PNG、JPG 或 WebP。")
    content = await upload.read(MAX_LOGO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Logo 文件为空。")
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo 文件不能超过 10 MB。")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Logo 图片无法读取。") from exc

    timestamp = now_iso()
    with get_connection() as conn:
        video = conn.execute("SELECT id FROM videos WHERE id = ?", (video_id,)).fetchone()
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在。")
        logo_dir = settings.upload_dir / "brand"
        logo_dir.mkdir(parents=True, exist_ok=True)
        slug = f"{timestamp.replace(':', '').replace('-', '').replace('+', '-')}-{uuid4().hex[:8]}"
        destination = logo_dir / f"video-{video_id}-{slug}{suffix}"
        destination.write_bytes(content)
        cursor = conn.execute(
            """
            INSERT INTO media_assets (
              video_id, kind, original_filename, stored_path, transcript_text,
              authorization_note, delete_after_processing, processing_status, created_at
            )
            VALUES (?, 'brand_logo', ?, ?, '', '用户上传的品牌 Logo。', 0, 'ready', ?)
            """,
            (video_id, filename, str(destination), timestamp),
        )
        asset = conn.execute("SELECT * FROM media_assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return media_asset_with_url(row_to_dict(asset))
