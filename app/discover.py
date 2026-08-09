from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

log = logging.getLogger("spider.discover")

GITHUB_API = "https://api.github.com/search/repositories"


def discover(top: int = 10, language: str = "C++", min_stars: int = 2000) -> list[dict]:
    """Search GitHub for popular open-source C/C++ repositories."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query = f"language:{language} stars:>{min_stars}"
    log.info("searching GitHub: %s", query)

    items: list[dict] = []
    page = 1
    while len(items) < top and page <= 10:
        resp = requests.get(
            GITHUB_API,
            params={
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(100, top),
                "page": page,
            },
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json().get("items", [])
        if not batch:
            break
        items.extend(batch)
        page += 1

    found: list[dict] = []
    for item in items[:top]:
        clone_url = item.get("clone_url") or item.get("html_url") or ""
        if not clone_url:
            continue
        found.append(
            {
                "name": item["name"],
                "repo": clone_url,
                "ref": item.get("default_branch", "main"),
                "description": (item.get("description") or "").strip(),
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "size_kb": item.get("size", 0),
                "pushed_at": item.get("pushed_at", ""),
            }
        )
    return found


def save_candidates(path: Path, repos: list[dict]) -> None:
    path.write_text(
        json.dumps(repos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("wrote %d candidates to %s", len(repos), path)
