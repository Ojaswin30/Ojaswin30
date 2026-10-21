#!/usr/bin/env python3
"""
Generates a comprehensive PRIVATE_INSIGHTS.md report covering:
1. Top Paths (Exact files & directories viewed)
2. Top Referrers (Traffic sources: Google, LinkedIn, etc.)
3. Active Engagement with Usernames & Timestamps:
   - Stargazers (User, Profile, Starred Date)
   - Forks (User, Fork URL, Date)
   - Watchers / Subscribers (Users tracking updates)
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime

def get_token():
    token = os.environ.get("TRAFFIC_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        proc = subprocess.Popen(
            ["git", "credential", "fill"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, _ = proc.communicate(input="protocol=https\nhost=github.com\n", timeout=5)
        for line in stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return None

def fetch_api(url, token, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "User-Agent": "GitHub-Private-Insights",
        "Authorization": f"Bearer {token}"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def format_date(iso_str):
    if not iso_str:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_str[:10]

def main():
    token = get_token()
    if not token:
        print("[!] Error: No GitHub token found. Please set TRAFFIC_TOKEN or log in with git credential manager.")
        sys.exit(1)

    user_info = fetch_api("https://api.github.com/user", token)
    username = user_info.get("login") if user_info else "Ojaswin30"

    print(f"Gathering private deep insights for @{username}...")

    repos = fetch_api("https://api.github.com/user/repos?type=owner&per_page=100&sort=updated", token)
    if not repos or not isinstance(repos, list):
        print("[!] Failed to retrieve repositories.")
        sys.exit(1)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md_lines = [
        "# 🕵️ Private Repository Insights & Telemetry",
        f"\n> **Generated**: `{now_str}` • **Account**: `@{username}`",
        "> *Note: This file contains private traffic sources and engaged user profiles. Keep it local / gitignored.*",
        "\n---",
        "## 📑 Table of Contents",
    ]

    toc_lines = []
    content_lines = []

    active_repo_count = 0

    for repo in repos:
        name = repo.get("name")
        if not name or repo.get("fork"):
            continue

        # 1. Fetch Views summary
        views_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/views", token)
        views = views_data.get("count", 0) if views_data else 0
        uniques = views_data.get("uniques", 0) if views_data else 0

        # 2. Fetch Top Paths
        paths_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/popular/paths", token) or []

        # 3. Fetch Referrers
        refs_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/popular/referrers", token) or []

        # 4. Fetch Stargazers with timestamp
        stargazers_data = fetch_api(
            f"https://api.github.com/repos/{username}/{name}/stargazers",
            token,
            accept="application/vnd.github.v3.star+json"
        ) or []

        # 5. Fetch Forks
        forks_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/forks", token) or []

        # 6. Fetch Watchers / Subscribers (filter out owner)
        watchers_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/subscribers", token) or []
        external_watchers = [w for w in watchers_data if w.get("login", "").lower() != username.lower()]

        # Only list repos that have any activity
        has_activity = (
            views > 0 or len(paths_data) > 0 or len(refs_data) > 0 or 
            len(stargazers_data) > 0 or len(forks_data) > 0 or len(external_watchers) > 0
        )

        if not has_activity:
            continue

        active_repo_count += 1
        anchor = name.lower().replace(".", "").replace("_", "-")
        toc_lines.append(f"- [{name}](#{anchor}) (`{views}` views, `{len(stargazers_data)}` stars, `{len(forks_data)}` forks)")

        section = [
            f"\n### <a id=\"{anchor}\"></a>📦 [{name}]({repo.get('html_url')})",
            f"**14-Day Traffic**: `{views}` total views | `{uniques}` unique visitors\n"
        ]

        # Top Paths Table
        section.append("#### 📂 Top Viewed Files & Paths (Last 14 Days)")
        if paths_data:
            section.append("| Path / File | Views | Unique Visitors |")
            section.append("| :--- | :---: | :---: |")
            for p in paths_data[:10]:
                path_str = p.get("path", "-")
                section.append(f"| `{path_str}` | {p.get('count', 0)} | {p.get('uniques', 0)} |")
        else:
            section.append("*No individual path data recorded in the last 14 days.*")
        section.append("")

        # Top Referrers Table
        section.append("#### 🌐 Traffic Referrers (Where visitors came from)")
        if refs_data:
            section.append("| Referrer Source | Total Views | Unique Visitors |")
            section.append("| :--- | :---: | :---: |")
            for r in refs_data:
                section.append(f"| **{r.get('referrer', '-')}** | {r.get('count', 0)} | {r.get('uniques', 0)} |")
        else:
            section.append("*No external referrers recorded.*")
        section.append("")

        # Actively Engaged Users (Stars, Forks, Watchers)
        section.append("#### 👤 Actively Engaged Users")
        
        # Stargazers
        if stargazers_data:
            section.append("**⭐ Stargazers**:")
            for s in stargazers_data:
                u = s.get("user", {})
                starred_at = format_date(s.get("starred_at"))
                user_login = u.get("login")
                user_url = u.get("html_url", f"https://github.com/{user_login}")
                section.append(f"- [@{user_login}]({user_url}) (starred on `{starred_at}`)")
        else:
            section.append("**⭐ Stargazers**: *None yet*")

        # Forks
        if forks_data:
            section.append("\n**🍴 Forked By**:")
            for f in forks_data:
                owner = f.get("owner", {})
                fork_user = owner.get("login")
                fork_url = f.get("html_url")
                created_at = format_date(f.get("created_at"))
                section.append(f"- [@{fork_user}]({owner.get('html_url')}) → [Fork Repo]({fork_url}) on `{created_at}`")
        else:
            section.append("**🍴 Forked By**: *None*")

        # External Watchers
        if external_watchers:
            section.append("\n**👀 Watchers / Subscribers**:")
            for w in external_watchers:
                w_login = w.get("login")
                w_url = w.get("html_url", f"https://github.com/{w_login}")
                section.append(f"- [@{w_login}]({w_url})")

        section.append("\n---")
        content_lines.extend(section)

    md_lines.extend(toc_lines)
    md_lines.append("\n---")
    md_lines.extend(content_lines)

    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "PRIVATE_INSIGHTS.md"))
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n[OK] Successfully generated {output_path}")
    print(f"[OK] Processed {active_repo_count} active repositories.")

if __name__ == "__main__":
    main()
