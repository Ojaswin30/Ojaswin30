#!/usr/bin/env python3
"""
Dynamically updates the 'Most Viewed Repositories' section in README.md
using GitHub's Traffic API (last 14 days of traffic stats).
Zero third-party dependencies (uses standard library urllib and json).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error

START_MARKER = "<!-- START_TOP_REPOS -->"
END_MARKER = "<!-- END_TOP_REPOS -->"
MEDALS = ["🥇", "🥈", "🥉", "4", "5"]

def fetch_github_api(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-Top-Repos-Updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"HTTPError {e.code} for {url}: {error_body}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None

def get_authenticated_username(token):
    data = fetch_github_api("https://api.github.com/user", token)
    if data and "login" in data:
        return data["login"]
    return os.environ.get("GITHUB_ACTOR", "Ojaswin30")

def get_top_viewed_repositories(token, username, limit=5):
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
        
        views = 0
        uniques = 0
        if traffic_data and isinstance(traffic_data, dict):
            views = traffic_data.get("count", 0)
            uniques = traffic_data.get("uniques", 0)

        description = repo.get("description") or "No description provided."
        # Clean description of pipe characters to preserve markdown table formatting
        description = description.replace("|", "\\|").strip()
        if len(description) > 90:
            description = description[:87] + "..."

        language = repo.get("language") or "General"

        repo_stats.append({
            "name": name,
            "html_url": repo.get("html_url", f"https://github.com/{username}/{name}"),
            "views": views,
            "uniques": uniques,
            "stars": repo.get("stargazers_count", 0),
            "language": language,
            "description": description
        })

    # Sort descending by views, then uniques, then stars
    repo_stats.sort(key=lambda r: (r["views"], r["uniques"], r["stars"]), reverse=True)
    return repo_stats[:limit]

def format_markdown_table(top_repos):
    if not top_repos:
        return "\n*No repository statistics available at this time.*\n"

    table_lines = [
        "",
        "| Rank | Repository | 14-Day Views | Unique Visitors | Language | Highlights |",
        "| :---: | :--- | :---: | :---: | :---: | :--- |"
    ]

    for i, repo in enumerate(top_repos):
        rank = MEDALS[i] if i < len(MEDALS) else str(i + 1)
        name_md = f"**[{repo['name']}]({repo['html_url']})**"
        views_md = f"`{repo['views']}`"
        uniques_md = f"`{repo['uniques']}`"
        lang_md = f"<code>{repo['language']}</code>"
        desc_md = repo["description"]
        table_lines.append(f"| {rank} | {name_md} | {views_md} | {uniques_md} | {lang_md} | {desc_md} |")

    table_lines.append("")
    table_lines.append("<div align=\"right\"><sub>*Auto-updated daily with live 14-day traffic from GitHub API*</sub></div>")
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
    # Preference: TRAFFIC_TOKEN (Personal Access Token), fallback: GITHUB_TOKEN
    token = os.environ.get("TRAFFIC_TOKEN") or os.environ.get("GITHUB_TOKEN")
    
    if not token:
        print("Warning: Neither TRAFFIC_TOKEN nor GITHUB_TOKEN environment variable found.", file=sys.stderr)
        print("Please provide a Personal Access Token with 'repo' scope in repository secrets.", file=sys.stderr)
        sys.exit(1)

    username = get_authenticated_username(token)
    print(f"Fetching repository traffic for user: {username}...")
    
    top_repos = get_top_viewed_repositories(token, username, limit=5)
    print(f"Found {len(top_repos)} repositories for ranking.")

    markdown_block = format_markdown_table(top_repos)
    readme_path = os.path.join(os.path.dirname(__file__), "..", "README.md")
    update_readme(markdown_block, readme_path=os.path.abspath(readme_path))

if __name__ == "__main__":
    main()
