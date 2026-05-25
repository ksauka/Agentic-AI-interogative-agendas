"""GitHub Saver Utility

Save user session data directly to a private GitHub repository using the GitHub API.
Requires a GitHub personal access token with repo permissions.
"""

import requests
import base64
import os
from typing import Optional


def save_to_github(
    repo: str,
    path: str,
    content: str,
    commit_message: str,
    github_token: str,
) -> tuple[bool, Optional[str]]:
    """
    Save content to a file in a GitHub repo (creates or updates the file).

    Args:
        repo: 'username/repo' (e.g., 'owner/hiring-study-data-private')
        path: path in the repo (e.g., 'sessions/2026-05-25/session_abc123.json')
        content: string content to save
        commit_message: commit message
        github_token: GitHub personal access token with repo scope

    Returns:
        (success, error_message) where error_message is None on success.
    """
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    sha = None

    # Check if file already exists (need SHA for update)
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json()["sha"]
        elif r.status_code not in (404,):
            print(f"Warning: GitHub preflight returned {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Warning: Could not check file existence: {e}")

    data: dict = {
        "message": commit_message,
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
    }
    if sha:
        data["sha"] = sha

    try:
        response = requests.put(api_url, json=data, headers=headers, timeout=30)
        if response.status_code in (200, 201):
            print(f"✅ Saved to GitHub: {path}")
            return True, None
        else:
            err = f"GitHub API error {response.status_code}: {response.text.strip()}"
            print(f"❌ {err}")
            return False, err
    except requests.exceptions.Timeout:
        print("❌ GitHub API timeout")
        return False, "GitHub API timeout while saving session data."
    except Exception as e:
        print(f"❌ GitHub save failed: {e}")
        return False, f"GitHub save failed: {e}"


def test_github_connection(github_token: str, repo: str) -> tuple[bool, str]:
    """Test GitHub API connection and repo access."""
    try:
        api_url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True, f"✅ Connected to {response.json()['full_name']}"
        elif response.status_code == 404:
            return False, f"❌ Repository '{repo}' not found or no access"
        elif response.status_code == 401:
            return False, "❌ Invalid GitHub token"
        else:
            return False, f"❌ GitHub API error: {response.status_code}"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)}"
