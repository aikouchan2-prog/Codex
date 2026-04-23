"""Send a message (text + optional image) to a Discord webhook."""
from __future__ import annotations

import mimetypes
from pathlib import Path

import requests


class SendError(Exception):
    pass


def send(webhook_url: str, content: str, image_path: str | Path | None) -> None:
    content = content or ""
    if not content and not image_path:
        raise SendError("Either content or image is required")

    data: dict[str, str] = {}
    if content:
        data["content"] = content

    files = None
    fh = None
    try:
        if image_path:
            path = Path(image_path)
            if not path.is_file():
                raise SendError(f"Image not found: {path}")
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            fh = path.open("rb")
            files = {"file": (path.name, fh, mime)}

        try:
            resp = requests.post(webhook_url, data=data, files=files, timeout=30)
        except requests.RequestException as e:
            raise SendError(f"Network error: {e}") from e

        if resp.status_code >= 400:
            raise SendError(f"Discord returned {resp.status_code}: {resp.text[:500]}")
    finally:
        if fh is not None:
            fh.close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Send a test message to a Discord webhook")
    p.add_argument("webhook_url")
    p.add_argument("--content", default="")
    p.add_argument("--image", default=None)
    args = p.parse_args()
    send(args.webhook_url, args.content, args.image)
    print("OK")
