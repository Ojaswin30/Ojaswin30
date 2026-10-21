#!/usr/bin/env python3
"""
View traffic statistics (views, uniques, clones, referrers) across ALL repositories.
Uses existing git credentials or TRAFFIC_TOKEN environment variable.
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

def get_token():
    token = os.environ.get("TRAFFIC_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token

    # Attempt to retrieve credentials from Git Credential Manager
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

def fetch_api(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-All-Stats-Viewer",
        "Authorization": f"Bearer {token}"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None

def main():
    token = get_token()
    if not token:
        print("\n[!] No GitHub token found.")
        print("Please set $env:TRAFFIC_TOKEN = '<your_token>' or log in via Git Credential Manager.\n")
        sys.exit(1)

    user_info = fetch_api("https://api.github.com/user", token)
    username = user_info.get("login") if user_info else "Ojaswin30"

    print(f"\nGathering live repository statistics for @{username}...")
    print("Fetching traffic data from GitHub API...\n")

    repos = fetch_api("https://api.github.com/user/repos?type=owner&per_page=100&sort=updated", token)
    if not repos or not isinstance(repos, list):
        print("[!] Could not fetch repository list.")
        sys.exit(1)

    stats = []
    total_views = 0
    total_uniques = 0
    total_clones = 0
    total_stars = 0

    for repo in repos:
        name = repo.get("name")
        if not name or repo.get("fork"):
            continue

        # Fetch Views
        views_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/views", token)
        views = views_data.get("count", 0) if views_data else 0
        uniques = views_data.get("uniques", 0) if views_data else 0

        # Fetch Clones
        clones_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/clones", token)
        clones = clones_data.get("count", 0) if clones_data else 0

        # Fetch Top Referrer
        refs_data = fetch_api(f"https://api.github.com/repos/{username}/{name}/traffic/popular/referrers", token)
        top_ref = refs_data[0].get("referrer") if refs_data and len(refs_data) > 0 else "-"

        stars = repo.get("stargazers_count", 0)
        language = repo.get("language") or "General"

        total_views += views
        total_uniques += uniques
        total_clones += clones
        total_stars += stars

        stats.append({
            "name": name,
            "views": views,
            "uniques": uniques,
            "clones": clones,
            "stars": stars,
            "ref": top_ref,
            "language": language
        })

    # Sort descending by views, then uniques, then clones, then stars
    stats.sort(key=lambda x: (x["views"], x["uniques"], x["clones"], x["stars"]), reverse=True)

    header = f"{'#':<3} | {'Repository':<36} | {'Views (14d)':<12} | {'Uniques':<9} | {'Clones':<8} | {'Stars':<6} | {'Top Referrer':<16} | {'Language':<10}"
    divider = "-" * len(header)

    print(header)
    print(divider)

    for i, s in enumerate(stats, 1):
        print(f"{i:<3} | {s['name']:<36} | {s['views']:<12} | {s['uniques']:<9} | {s['clones']:<8} | {s['stars']:<6} | {s['ref']:<16} | {s['language']:<10}")

    print(divider)
    print(f"{'TOTAL ACROSS ALL REPOSITORIES':<42} | {total_views:<12} | {total_uniques:<9} | {total_clones:<8} | {total_stars:<6} |")
    print("\nNote: Views and Unique Visitors are trailing 14-day counts provided by GitHub Insights.\n")

if __name__ == "__main__":
    main()
