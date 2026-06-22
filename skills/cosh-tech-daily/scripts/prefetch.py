#!/usr/bin/env python3
"""Prefetch public signals for Cosh Tech Daily.

The script intentionally uses only Python's standard library so it can run in
minimal Codex environments. Network failures are captured in the JSON output
instead of raising, allowing the skill user to fall back source-by-source.
"""

from __future__ import annotations

import concurrent.futures
import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

TIMEOUT_SECONDS = 12
USER_AGENT = "cosh-tech-daily-prefetch/1.0"
DEFAULT_CONFIG = {
    "profile": "standard",
    "source_bias": "mixed",
    "style": "editorial",
    "interests": {
        "max_generated_queries": 8,
        "topics": [
            "AI agents",
            "coding agents",
            "developer tools",
            "open source AI",
            "LLM applications",
        ],
        "keywords": ["Codex", "Claude Code", "MCP", "RAG", "workflow automation"],
        "companies": [
            "OpenAI",
            "Anthropic",
            "Google DeepMind",
            "阿里",
            "字节",
            "腾讯",
            "百度",
            "智谱",
            "月之暗面",
        ],
        "models_or_projects": ["GPT", "Claude", "Gemini", "DeepSeek", "Qwen", "Kimi"],
        "preferred_domains": [
            "openai.com",
            "anthropic.com",
            "deepmind.google",
            "github.com",
            "huggingface.co",
            "arxiv.org",
        ],
        "exclude_keywords": ["SEO", "代发", "博彩", "币圈喊单"],
        "exclude_domains": ["instagram.com", "facebook.com"],
    },
    "search_cosh": {
        "enabled": True,
        "base_url": "https://search.cosh.fun",
        "category": "general",
        "time_range": "day",
        "language": "auto",
        "limit_per_query": 3,
    },
    "weather": {
        "enabled": True,
        "provider": "wttr.in",
        "cities": [
            {"name": "北京", "query": "Beijing"},
            {"name": "广州", "query": "Guangzhou"},
        ],
    },
    "sections": {
        "ai_products": {"enabled": True, "limit": 6},
        "github_trending": {"enabled": True, "limit": 5},
        "important_news": {"enabled": True, "limit": 8},
        "daily_observations": {"enabled": True, "limit": 3},
        "weather": {"enabled": True, "limit": 2},
    },
    "news_queries": [
        "AI OR OpenAI OR Anthropic OR Google DeepMind when:1d",
        "developer tools OR GitHub OR programming OR open source when:1d",
        "LLM model release OR AI agent OR coding agent when:1d",
        "阿里 AI OR 字节 AI OR 腾讯 AI OR 百度 AI OR 智谱 AI OR 月之暗面 when:1d",
    ],
    "fallback_search_queries": [
        "today AI model release developer tools",
        "GitHub trending AI developer tools today",
        "OpenAI Anthropic Google DeepMind developer news today",
        "AI coding agent open source release today",
        "阿里 字节 腾讯 百度 智谱 月之暗面 AI 今日",
    ],
}


def load_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    if not config_path.exists():
        return DEFAULT_CONFIG

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)

    config = json.loads(json.dumps(DEFAULT_CONFIG))
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


def merge_list_values(*values: list[str]) -> list[str]:
    merged = []
    seen = set()
    for value_list in values:
        for value in value_list or []:
            normalized = value.strip()
            if normalized and normalized.lower() not in seen:
                merged.append(normalized)
                seen.add(normalized.lower())
    return merged


def interest_terms(config: dict) -> list[str]:
    interests = config.get("interests", {})
    return merge_list_values(
        interests.get("topics", []),
        interests.get("keywords", []),
        interests.get("companies", []),
        interests.get("models_or_projects", []),
    )


def generated_interest_queries(config: dict) -> list[str]:
    terms = interest_terms(config)
    if not terms:
        return []

    max_queries = int(config.get("interests", {}).get("max_generated_queries", 8))
    queries = []
    for term in terms[:max_queries]:
        queries.append(f"{term} AI developer news when:1d")

    preferred_domains = config.get("interests", {}).get("preferred_domains", [])
    for domain in preferred_domains[: max(0, max_queries // 2)]:
        queries.append(f"site:{domain} AI OR developer OR release when:7d")

    return queries


def configured_news_queries(config: dict) -> list[str]:
    return merge_list_values(
        config.get("news_queries", DEFAULT_CONFIG["news_queries"]),
        generated_interest_queries(config),
    )


def configured_search_queries(config: dict) -> list[str]:
    interests = interest_terms(config)
    max_queries = int(config.get("interests", {}).get("max_generated_queries", 8))
    interest_queries = [
        f"{term} latest AI developer news" for term in interests[:max_queries]
    ]
    return merge_list_values(
        config.get("fallback_search_queries", DEFAULT_CONFIG["fallback_search_queries"]),
        interest_queries,
    )


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.URLError:
        result = subprocess.run(
            [
                "curl",
                "-fsSL",
                "--max-time",
                str(TIMEOUT_SECONDS),
                "-A",
                USER_AGENT,
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def absolute_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, href)


def fetch_product_hunt() -> list[dict[str, str | int | None]]:
    url = "https://www.producthunt.com/"
    html = fetch_text(url)
    items: list[dict[str, str | int | None]] = []
    seen: set[str] = set()

    for match in re.finditer(r'href="(/posts/[^"#?]+)"[^>]*>(.*?)</a>', html):
        href, raw_title = match.groups()
        title = strip_html(raw_title)
        if not title or title in seen:
            continue
        seen.add(title)
        items.append(
            {
                "name": title,
                "url": absolute_url(url, href),
                "source": "Product Hunt",
                "votes": None,
            }
        )
        if len(items) >= 15:
            break

    return items


def fetch_github_trending() -> list[dict[str, str | int | None]]:
    url = "https://github.com/trending?since=daily"
    html = fetch_text(url)
    items: list[dict[str, str | int | None]] = []

    article_pattern = re.compile(r"<article[\s\S]*?</article>", re.IGNORECASE)
    repo_pattern = re.compile(r'href="/([^"/\s]+/[^"/\s]+)"')
    desc_pattern = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>([\s\S]*?)</p>')
    lang_pattern = re.compile(r'itemprop="programmingLanguage">([^<]+)</span>')
    stars_pattern = re.compile(r'aria-label="star"[\s\S]*?</svg>\s*([0-9,]+)')
    today_pattern = re.compile(r"([0-9,]+)\s+stars?\s+today")

    for article in article_pattern.findall(html):
        repo_match = repo_pattern.search(article)
        if not repo_match:
            continue
        repo = repo_match.group(1)
        desc_match = desc_pattern.search(article)
        lang_match = lang_pattern.search(article)
        stars_match = stars_pattern.search(article)
        today_match = today_pattern.search(article)
        items.append(
            {
                "repo": repo,
                "url": f"https://github.com/{repo}",
                "description": strip_html(desc_match.group(1)) if desc_match else "",
                "language": strip_html(lang_match.group(1)) if lang_match else None,
                "stars": strip_html(stars_match.group(1)) if stars_match else None,
                "stars_today": strip_html(today_match.group(1)) if today_match else None,
            }
        )
        if len(items) >= 15:
            break

    return items


def parse_rss(feed_url: str, source: str, limit: int = 8) -> list[dict[str, str]]:
    xml_text = fetch_text(feed_url)
    root = ET.fromstring(xml_text)
    items: list[dict[str, str]] = []

    for item in root.findall(".//item")[:limit]:
        title = strip_html(item.findtext("title", ""))
        link = strip_html(item.findtext("link", ""))
        published = strip_html(item.findtext("pubDate", ""))
        summary = strip_html(item.findtext("description", ""))
        if title and link:
            items.append(
                {
                    "title": title,
                    "url": link,
                    "published": published,
                    "summary": summary,
                    "source": source,
                }
            )

    return items


def google_news_rss(query: str) -> str:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "hl": "zh-CN",
            "gl": "CN",
            "ceid": "CN:zh-Hans",
        }
    )
    return f"https://news.google.com/rss/search?{params}"


def search_cosh_url(config: dict, query: str, result_format: str = "json") -> str:
    search_config = config.get("search_cosh", DEFAULT_CONFIG["search_cosh"])
    base_url = search_config.get("base_url", "https://search.cosh.fun").rstrip("/")
    params = urllib.parse.urlencode(
        {
            "q": query,
            "categories": search_config.get("category", "general"),
            "pageno": 1,
            "time_range": search_config.get("time_range", "day"),
            "language": search_config.get("language", "auto"),
            "safesearch": 0,
            "format": result_format,
        }
    )
    return f"{base_url}/search?{params}"


def fetch_search_cosh(config: dict) -> dict:
    search_config = config.get("search_cosh", DEFAULT_CONFIG["search_cosh"])
    limit = int(search_config.get("limit_per_query", 5))
    output = {
        "base_url": search_config.get("base_url", "https://search.cosh.fun"),
        "category": search_config.get("category", "general"),
        "time_range": search_config.get("time_range", "day"),
        "queries": [],
        "unresponsive_engines": [],
    }

    for query in configured_search_queries(config):
        payload = fetch_json(search_cosh_url(config, query, "json"))
        results = []
        for item in payload.get("results", [])[:limit]:
            title = strip_html(item.get("title", ""))
            url = item.get("url", "")
            content = strip_html(item.get("content", ""))
            if title and url:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "summary": content,
                        "engine": item.get("engine") or item.get("engines"),
                        "source": "search.cosh.fun",
                    }
                )
        output["queries"].append({"query": query, "results": results})
        output["unresponsive_engines"].extend(payload.get("unresponsive_engines", []))

    return output


def wttr_url(city_query: str) -> str:
    encoded = urllib.parse.quote(city_query)
    return f"https://wttr.in/{encoded}?format=j1"


def fetch_weather_city(city: dict) -> dict:
    payload = fetch_json(wttr_url(city["query"]))
    current = payload.get("current_condition", [{}])[0]
    forecast = payload.get("weather", [])
    today = forecast[0] if forecast else {}
    tomorrow = forecast[1] if len(forecast) > 1 else {}

    return {
        "name": city["name"],
        "query": city["query"],
        "current": {
            "temp_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "humidity": current.get("humidity"),
            "wind_kmph": current.get("windspeedKmph"),
            "description": (
                current.get("weatherDesc", [{}])[0].get("value")
                if current.get("weatherDesc")
                else None
            ),
        },
        "today": {
            "date": today.get("date"),
            "min_c": today.get("mintempC"),
            "max_c": today.get("maxtempC"),
            "uv_index": today.get("uvIndex"),
        },
        "tomorrow": {
            "date": tomorrow.get("date"),
            "min_c": tomorrow.get("mintempC"),
            "max_c": tomorrow.get("maxtempC"),
            "uv_index": tomorrow.get("uvIndex"),
        },
        "source": "wttr.in",
    }


def fetch_weather(config: dict) -> list[dict]:
    weather_config = config.get("weather", DEFAULT_CONFIG["weather"])
    cities = weather_config.get("cities", DEFAULT_CONFIG["weather"]["cities"])
    return [fetch_weather_city(city) for city in cities]


def fetch_news(config: dict) -> list[dict[str, str]]:
    news: list[dict[str, str]] = []
    for query in configured_news_queries(config):
        source = f"Google News: {query}"
        url = google_news_rss(query)
        news.extend(parse_rss(url, source, limit=6))
    return news


def run_source(name: str, fn):
    try:
        return name, fn(), None
    except (
        urllib.error.URLError,
        subprocess.CalledProcessError,
        TimeoutError,
        ET.ParseError,
        OSError,
    ) as exc:
        return name, None, f"{type(exc).__name__}: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prefetch data for Cosh Tech Daily.")
    parser.add_argument(
        "--only",
        choices=["weather"],
        help="Fetch only one source for quick checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config()
    sections = config.get("sections", {})
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "product_hunt": [],
        "github_trending": [],
        "news": [],
        "search_cosh": {},
        "weather": [],
        "search_queries": configured_search_queries(config),
        "errors": {},
    }

    sources = {}
    if args.only == "weather":
        sources["weather"] = lambda: fetch_weather(config)
    elif sections.get("ai_products", {}).get("enabled", True):
        sources["product_hunt"] = fetch_product_hunt
        if sections.get("github_trending", {}).get("enabled", True):
            sources["github_trending"] = fetch_github_trending
        if sections.get("important_news", {}).get("enabled", True):
            sources["news"] = lambda: fetch_news(config)
            if config.get("search_cosh", {}).get("enabled", True):
                sources["search_cosh"] = lambda: fetch_search_cosh(config)
        if (
            sections.get("weather", {}).get("enabled", True)
            and config.get("weather", {}).get("enabled", True)
        ):
            sources["weather"] = lambda: fetch_weather(config)

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_source, name, fn) for name, fn in sources.items()]
        for future in concurrent.futures.as_completed(futures):
            name, data, error = future.result()
            output[name] = data or ({} if name == "search_cosh" else [])
            output["errors"][name] = error

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
