#!/usr/bin/env python3
"""Upload one generated image to Alibaba Cloud OSS with OSS Python SDK V2."""

from __future__ import annotations

import argparse
import mimetypes
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlparse


def load_local_env() -> None:
    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"]
    for env_file in candidates:
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.removeprefix("export ").strip()
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)
        return


load_local_env()


REQUIRED_ENV = (
    "OSS_ENDPOINT",
    "OSS_BUCKET",
)


def require_env() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    has_access_key = (
        os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")
        and os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    ) or (os.getenv("OSS_ACCESS_KEY_ID") and os.getenv("OSS_ACCESS_KEY_SECRET"))
    if not has_access_key:
        missing.append(
            "ALIBABA_CLOUD_ACCESS_KEY_ID/ALIBABA_CLOUD_ACCESS_KEY_SECRET "
            "or OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET"
        )
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
        "--endpoint",
        default=os.getenv("OSS_ENDPOINT"),
        help="OSS endpoint, for example https://oss-cn-hangzhou.aliyuncs.com. Defaults to OSS_ENDPOINT.",
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


def infer_region_from_endpoint(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    parsed = urlparse(endpoint if "://" in endpoint else f"//{endpoint}")
    host = (parsed.hostname or "").lower()
    match = re.search(r"(?:^|\.)oss-([a-z0-9-]+?)(?:-internal)?\.aliyuncs\.com$", host)
    if not match:
        return None
    region = match.group(1)
    return None if region.startswith("accelerate") else region


def build_object_url(endpoint: str, bucket: str, object_key: str) -> str:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    scheme = parsed.scheme or "https"
    host = parsed.netloc or parsed.path
    if not host:
        raise SystemExit("Cannot build OSS URL because endpoint host is empty.")
    normalized_key = quote(object_key.lstrip("/"), safe="/")
    return f"{scheme}://{bucket}.{host.rstrip('/')}/{normalized_key}"


def access_key_pair() -> tuple[str, str]:
    access_key_id = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID") or os.getenv("OSS_ACCESS_KEY_ID")
    access_key_secret = os.getenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET") or os.getenv(
        "OSS_ACCESS_KEY_SECRET"
    )
    if not access_key_id or not access_key_secret:
        raise SystemExit("Missing OSS access key credentials.")
    return access_key_id, access_key_secret


def main() -> int:
    args = parse_args()
    require_env()
    region = infer_region_from_endpoint(args.endpoint)
    if not region:
        raise SystemExit(
            "Cannot infer OSS region from OSS_ENDPOINT. Use a standard OSS endpoint "
            "such as https://oss-cn-hangzhou.aliyuncs.com."
        )

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

    access_key_id, access_key_secret = access_key_pair()
    credentials_provider = oss.credentials.StaticCredentialsProvider(
        access_key_id,
        access_key_secret,
        os.getenv("OSS_SESSION_TOKEN"),
    )
    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = region
    cfg.endpoint = args.endpoint
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
    print(build_object_url(args.endpoint, args.bucket, object_key))
    print(f"status_code={result.status_code}", file=sys.stderr)
    print(f"request_id={result.request_id}", file=sys.stderr)
    print(f"object_key={object_key}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
