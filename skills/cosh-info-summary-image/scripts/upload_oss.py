#!/usr/bin/env python3
"""Upload one generated image to Alibaba Cloud OSS with OSS Python SDK V2."""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path


REQUIRED_ENV = (
    "ALIBABA_CLOUD_ACCESS_KEY_ID",
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
    "OSS_REGION",
    "OSS_BUCKET",
)


def require_env() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: " + ", ".join(missing)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Local image path to upload.")
    parser.add_argument(
        "--key",
        help="OSS object key. If omitted, OSS_PREFIX plus the local filename is used.",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("OSS_PREFIX", "generated-images"),
        help="OSS object key prefix when --key is omitted.",
    )
    parser.add_argument(
        "--bucket",
        default=os.getenv("OSS_BUCKET"),
        help="OSS bucket name. Defaults to OSS_BUCKET.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("OSS_REGION"),
        help="OSS region, for example cn-hangzhou. Defaults to OSS_REGION.",
    )
    parser.add_argument(
        "--forbid-overwrite",
        action="store_true",
        help="Fail if the target object already exists.",
    )
    return parser.parse_args()


def build_object_key(args: argparse.Namespace, local_file: Path) -> str:
    if args.key:
        return args.key.lstrip("/")
    prefix = (args.prefix or "").strip("/")
    return f"{prefix}/{local_file.name}" if prefix else local_file.name


def main() -> int:
    require_env()
    args = parse_args()
    local_file = Path(args.file)
    if not local_file.is_file():
        raise SystemExit(f"Local file does not exist: {local_file}")

    try:
        import alibabacloud_oss_v2 as oss
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install with `pip install alibabacloud-oss-v2`."
        ) from exc

    object_key = build_object_key(args, local_file)
    content_type = mimetypes.guess_type(local_file.name)[0] or "application/octet-stream"

    credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = args.region
    client = oss.Client(cfg)

    result = client.put_object_from_file(
        oss.PutObjectRequest(
            bucket=args.bucket,
            key=object_key,
            content_type=content_type,
            forbid_overwrite=args.forbid_overwrite,
        ),
        str(local_file),
    )
    print(object_key)
    print(f"status_code={result.status_code}", file=sys.stderr)
    print(f"request_id={result.request_id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
