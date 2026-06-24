"""Send one archived card to Typefully as an X draft.

This script is intentionally opt-in. Set TYPEFULLY_CREATE_DRAFT=true to create
the draft; otherwise it prints a dry-run preview and exits.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
POSTS_FILE = ROOT_DIR / "data" / "posts.json"
BASE_URL = "https://api.typefully.com/v2"


def env_flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def load_posts() -> list[dict[str, Any]]:
    if not POSTS_FILE.exists():
        return []
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def image_path(post: dict[str, Any]) -> Path:
    image = str(post.get("image") or "").lstrip("/")
    if not image:
        raise RuntimeError(f"Post {post.get('id')} does not include an image")
    path = ROOT_DIR / "public" / image
    if not path.exists():
        raise RuntimeError(f"Image not found for post {post.get('id')}: {path}")
    return path


def selected_post(posts: list[dict[str, Any]]) -> dict[str, Any]:
    post_id = os.environ.get("TYPEFULLY_POST_ID", "").strip()
    if not post_id:
        raise RuntimeError("TYPEFULLY_POST_ID is required")

    matches = [post for post in posts if post.get("id") == post_id]
    if not matches:
        raise RuntimeError(f"Post id not found: {post_id}")
    return matches[0]


def api_key() -> str:
    value = os.environ.get("TYPEFULLY_API_KEY", "").strip()
    if not value:
        raise RuntimeError("TYPEFULLY_API_KEY is required")
    return value


def social_set_id() -> str:
    value = (
        os.environ.get("TYPEFULLY_SOCIAL_SET_ID_INPUT", "").strip()
        or os.environ.get("TYPEFULLY_SOCIAL_SET_ID", "").strip()
    )
    if not value:
        raise RuntimeError("TYPEFULLY_SOCIAL_SET_ID is required")
    return value


def request_json(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    import requests

    response = requests.request(
        method,
        f"{BASE_URL}{endpoint}",
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Typefully API {response.status_code}: {response.text}")
    if not response.text:
        return {}
    return response.json()


def upload_to_presigned_url(upload_url: str, media_path: Path) -> None:
    import requests

    response = requests.put(upload_url, data=media_path.read_bytes(), timeout=60)
    if response.status_code not in {200, 204}:
        raise RuntimeError(f"Media upload failed {response.status_code}: {response.text}")


def upload_media(set_id: str, media_path: Path) -> str:
    upload = request_json(
        "POST",
        f"/social-sets/{set_id}/media/upload",
        {"file_name": media_path.name},
    )
    media_id = str(upload["media_id"])
    upload_to_presigned_url(str(upload["upload_url"]), media_path)
    wait_for_media(set_id, media_id)
    return media_id


def wait_for_media(set_id: str, media_id: str) -> None:
    for _ in range(30):
        status = request_json("GET", f"/social-sets/{set_id}/media/{media_id}")
        media_status = status.get("status")
        print(f"Media status: {media_status}")
        if media_status == "ready":
            return
        if media_status == "failed":
            raise RuntimeError(f"Typefully media processing failed: {status}")
        time.sleep(2)
    raise RuntimeError("Timed out waiting for Typefully media processing")


def create_draft(set_id: str, tweet_text: str, media_id: str) -> dict[str, Any]:
    payload = {
        "platforms": {
            "x": {
                "enabled": True,
                "posts": [
                    {
                        "text": tweet_text,
                        "media_ids": [media_id],
                    }
                ],
            }
        }
    }
    return request_json("POST", f"/social-sets/{set_id}/drafts", payload)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    posts = load_posts()
    post = selected_post(posts)
    tweet_text = str(post.get("tweet") or "")
    if not tweet_text:
        raise RuntimeError(f"Post {post.get('id')} does not include tweet text")
    if len(tweet_text) > 280:
        raise RuntimeError(f"Post {post.get('id')} tweet is {len(tweet_text)} characters")

    media_path = image_path(post)
    media_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    should_create = env_flag("TYPEFULLY_CREATE_DRAFT")

    print(f"Selected post: {post['id']}")
    print(f"Title: {post.get('title')}")
    print(f"Tweet length: {len(tweet_text)} chars")
    print(f"Image: {media_path.name} ({media_type})")
    print("Tweet preview:")
    print(tweet_text)

    if not should_create:
        print("TYPEFULLY_CREATE_DRAFT is not true. Dry run only; no Typefully draft was created.")
        return

    set_id = social_set_id()
    media_id = upload_media(set_id, media_path)
    draft = create_draft(set_id, tweet_text, media_id)
    draft_id = draft.get("draft_id") or draft.get("id")
    draft_url = draft.get("share_url") or (f"https://typefully.com/?d={draft_id}" if draft_id else "")

    post["typefullyDraftId"] = draft_id
    post["typefullyDraftUrl"] = draft_url
    POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Typefully draft created.")
    print(f"Draft ID: {draft_id}")
    if draft_url:
        print(f"Draft URL: {draft_url}")


if __name__ == "__main__":
    main()
