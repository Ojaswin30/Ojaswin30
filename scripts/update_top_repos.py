#!/usr/bin/env python3
"""
Dynamically updates the 'Most Viewed Repositories' section in README.md
using GitHub's Traffic API. Tracks all-time cumulative views across runs
and shows:
- Total Views
- Views (Last 14 Days)
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

START_MARKER = "<!-- START_TOP_REPOS -->"
END_MARKER = "<!-- END_TOP_REPOS -->"

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

def fetch_github_api(url, token, retries=2):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-Top-Repos-Updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            print(f"HTTPError {e.code} for {url}: {error_body}", file=sys.stderr)
            return None
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error fetching {url}: {e}", file=sys.stderr)
                return None

def get_authenticated_username(token):
    data = fetch_github_api("https://api.github.com/user", token)
    if data and "login" in data:
        return data["login"]
    return os.environ.get("GITHUB_ACTOR", "Ojaswin30")

def load_traffic_history(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_traffic_history(history, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def get_top_viewed_repositories(token, username, history_path, limit=5):
    history = load_traffic_history(history_path)

    # Try fetching user's owned repositories via /user/repos, fallback to /users/{username}/repos
    repos_url = "https://api.github.com/user/repos?type=owner&per_page=100&sort=updated"
    repos = fetch_github_api(repos_url, token)
    
    if not repos or not isinstance(repos, list):
        print("Falling back to public repos endpoint...", file=sys.stderr)
        repos_url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
        repos = fetch_github_api(repos_url, token)

    if not repos or not isinstance(repos, list):
        print("Failed to retrieve repositories.", file=sys.stderr)
        return []

    repo_stats = []

    for repo in repos:
        name = repo.get("name")
        # Skip the profile README repository itself and forks
        if not name or name.lower() == username.lower() or repo.get("fork"):
            continue

        traffic_url = f"https://api.github.com/repos/{username}/{name}/traffic/views"
        traffic_data = fetch_github_api(traffic_url, token)
        
        views_14d = 0
        uniques_14d = 0
        if traffic_data and isinstance(traffic_data, dict):
            views_14d = traffic_data.get("count", 0)
            uniques_14d = traffic_data.get("uniques", 0)

            # Update persistent cumulative daily history
            if name not in history:
                history[name] = {"daily": {}}
            daily_dict = history[name].setdefault("daily", {})
            for day in traffic_data.get("views", []):
                t_key = day.get("timestamp", "")[:10]
                if t_key:
                    daily_dict[t_key] = max(daily_dict.get(t_key, 0), day.get("count", 0))

        # Calculate all-time views from accumulated history (at minimum equal to 14d views)
        if name in history and "daily" in history[name] and history[name]["daily"]:
            total_views = sum(history[name]["daily"].values())
        else:
            total_views = views_14d

        repo_stats.append({
            "name": name,
            "html_url": repo.get("html_url", f"https://github.com/{username}/{name}"),
            "views_14d": views_14d,
            "total_views": total_views,
            "uniques_14d": uniques_14d,
            "stars": repo.get("stargazers_count", 0),
        })

    save_traffic_history(history, history_path)

    # Sort descending by views in last 14 days, then total views, then stars
    repo_stats.sort(key=lambda r: (r["views_14d"], r["total_views"], r["stars"]), reverse=True)
    return repo_stats[:limit]

def format_markdown_table(top_repos):
    if not top_repos:
        return "\n*No repository statistics available at this time.*\n"

    table_lines = [
        "",
        "| Repository | Total Views | Views (Last 14 Days) |",
        "| :--- | :---: | :---: |"
    ]

    for repo in top_repos:
        name_md = f"**[{repo['name']}]({repo['html_url']})**"
        total_views_md = f"`{repo['total_views']}`"
        views_14d_md = f"`{repo['views_14d']}`"
        table_lines.append(f"| {name_md} | {total_views_md} | {views_14d_md} |")

    table_lines.append("")
    table_lines.append("<div align=\"right\"><sub>*Auto-updated daily via GitHub Actions*</sub></div>")
    table_lines.append("")
    return "\n".join(table_lines)

def update_readme(new_content_block, readme_path="README.md"):
    if not os.path.exists(readme_path):
        print(f"Error: {readme_path} not found.", file=sys.stderr)
        return False

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        f"({re.escape(START_MARKER)})(.*?)({re.escape(END_MARKER)})",
        re.DOTALL
    )

    if not pattern.search(content):
        print(f"Error: Markers {START_MARKER} and {END_MARKER} not found in {readme_path}", file=sys.stderr)
        return False

    replacement = f"{START_MARKER}\n{new_content_block}\n{END_MARKER}"
    updated_content = pattern.sub(replacement, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print("Successfully updated README.md with latest repository stats.")
    return True

def main():
    token = get_token()
    
    if not token:
        print("Warning: Neither TRAFFIC_TOKEN nor GITHUB_TOKEN environment variable found.", file=sys.stderr)
        print("Please provide a Personal Access Token with 'repo' scope in repository secrets.", file=sys.stderr)
        sys.exit(1)

    username = get_authenticated_username(token)
    print(f"Fetching repository traffic for user: {username}...")
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    history_path = os.path.join(root_dir, "data", "traffic_history.json")
    readme_path = os.path.join(root_dir, "README.md")

    top_repos = get_top_viewed_repositories(token, username, history_path, limit=5)
    print(f"Found {len(top_repos)} repositories for ranking.")

    markdown_block = format_markdown_table(top_repos)
    update_readme(markdown_block, readme_path=readme_path)

if __name__ == "__main__":
    main()
