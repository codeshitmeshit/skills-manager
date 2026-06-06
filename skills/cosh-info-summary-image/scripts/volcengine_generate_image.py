#!/usr/bin/env python3
"""Generate one image through Volcengine Ark image generation fallback."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


REQUIRED_ENV = ("VOLCENGINE_API_KEY", "VOLCENGINE_IMAGE_MODEL")


def require_env() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: " + ", ".join(missing)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, help="Final image prompt.")
    parser.add_argument(
        "--output",
        default="summary-image.png",
        help="Local output file path.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3/"),
        help="Ark OpenAI-compatible base URL.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("VOLCENGINE_IMAGE_MODEL"),
        help="Image model or endpoint ID. Defaults to VOLCENGINE_IMAGE_MODEL.",
    )
    parser.add_argument(
        "--size",
        default=os.getenv("VOLCENGINE_IMAGE_SIZE", "16:9"),
        help="Requested image size or aspect ratio.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=int(os.getenv("VOLCENGINE_TIMEOUT", "180")),
        help="Request timeout in seconds.",
    )
    return parser.parse_args()


def first_image_payload(payload: dict) -> dict:
    data = payload.get("data")
    if isinstance(data, list) and data:
        if isinstance(data[0], dict):
            return data[0]
    if isinstance(payload.get("result"), dict):
        return payload["result"]
    raise SystemExit("No image data found in response: " + json.dumps(payload, ensure_ascii=False)[:1000])


def write_image(image: dict, output: Path, timeout: int) -> None:
    b64 = image.get("b64_json") or image.get("base64") or image.get("image_base64")
    if b64:
        output.write_bytes(base64.b64decode(b64))
        return

    url = image.get("url") or image.get("image_url")
    if url:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        output.write_bytes(response.content)
        return

    raise SystemExit("Unsupported image response item: " + json.dumps(image, ensure_ascii=False)[:1000])


def main() -> int:
    require_env()
    args = parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    endpoint = urljoin(args.base_url.rstrip("/") + "/", "images/generations")
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {os.environ['VOLCENGINE_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": args.model,
            "prompt": args.prompt,
            "size": args.size,
            "response_format": "b64_json",
            "n": 1,
        },
        timeout=args.timeout,
    )
    response.raise_for_status()
    payload = response.json()
    write_image(first_image_payload(payload), output, args.timeout)
    print(str(output))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(exc.response.text, file=sys.stderr)
        raise
