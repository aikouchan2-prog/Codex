"""Discord scheduled-post web UI (Flask)."""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

import db
import scheduler

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # Discord webhook default limit

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1 * 1024 * 1024
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_urlsafe(32)


def _parse_local_datetime_to_utc(value: str) -> datetime:
    """Parse an <input type=datetime-local> value (local wall time) into UTC."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


@app.route("/")
def index():
    posts = db.list_posts()
    default_webhook = os.environ.get("DEFAULT_WEBHOOK_URL", "")
    return render_template(
        "index.html",
        posts=posts,
        default_webhook=default_webhook,
    )


@app.route("/schedule", methods=["POST"])
def schedule():
    webhook_url = (request.form.get("webhook_url") or "").strip()
    content = (request.form.get("content") or "").strip()
    scheduled_at_raw = (request.form.get("scheduled_at") or "").strip()
    image = request.files.get("image")

    if not webhook_url.startswith("https://"):
        flash("Webhook URL は https:// で始まる URL を入力してください。", "error")
        return redirect(url_for("index"))
    if not scheduled_at_raw:
        flash("送信日時を指定してください。", "error")
        return redirect(url_for("index"))

    has_image = image is not None and image.filename
    if not content and not has_image:
        flash("本文または画像のどちらかは必須です。", "error")
        return redirect(url_for("index"))

    try:
        scheduled_at_utc = _parse_local_datetime_to_utc(scheduled_at_raw)
    except ValueError:
        flash("送信日時の形式が不正です。", "error")
        return redirect(url_for("index"))

    if scheduled_at_utc <= datetime.now(timezone.utc):
        flash("送信日時は未来の時刻を指定してください。", "error")
        return redirect(url_for("index"))

    image_path: str | None = None
    if has_image:
        original = secure_filename(image.filename) or "upload"
        ext = Path(original).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            flash(
                f"対応していない画像形式です ({ext})。{', '.join(sorted(ALLOWED_IMAGE_EXTS))} のみ使えます。",
                "error",
            )
            return redirect(url_for("index"))
        saved_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = UPLOAD_DIR / saved_name
        image.save(saved_path)
        if saved_path.stat().st_size > MAX_IMAGE_BYTES:
            saved_path.unlink(missing_ok=True)
            flash("画像サイズが 8MB を超えています。", "error")
            return redirect(url_for("index"))
        image_path = str(saved_path)

    post_id = db.create_post(webhook_url, content, image_path, scheduled_at_utc)
    flash(f"予約 #{post_id} を登録しました。", "success")
    return redirect(url_for("index"))


@app.route("/cancel/<int:post_id>", methods=["POST"])
def cancel(post_id: int):
    if db.cancel_post(post_id):
        flash(f"予約 #{post_id} をキャンセルしました。", "success")
    else:
        flash(f"予約 #{post_id} はキャンセルできませんでした（既に送信済み等）。", "error")
    return redirect(url_for("index"))


@app.route("/uploads/<path:name>")
def uploaded_file(name: str):
    safe = secure_filename(name)
    if not safe or safe != name:
        abort(404)
    if not (UPLOAD_DIR / safe).is_file():
        abort(404)
    return send_from_directory(UPLOAD_DIR, safe)


@app.template_filter("to_local_display")
def to_local_display(iso_utc: str | None) -> str:
    """Render a stored UTC ISO string as a browser-local timestamp via JS hook."""
    if not iso_utc:
        return ""
    return iso_utc


def create_app() -> Flask:
    db.init_db()
    scheduler.start()
    return app


if __name__ == "__main__":
    create_app()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False, use_reloader=False)
