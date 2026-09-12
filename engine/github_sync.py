"""Commit files back to GitHub through the Contents API.

Spec addition (V1-0b). No Streamlit imports; stdlib only, so nothing new is
added to requirements.txt.

Why this exists: Streamlit Community Cloud has an ephemeral filesystem, so the
app cannot persist anything itself. Without this module the user must download
each changed file and commit it by hand. With a personal access token in
Streamlit secrets, the app can do that commit for them.

SECURITY. The token is a write credential for the repository. It belongs in
`.streamlit/secrets.toml` (git-ignored locally) or the Streamlit Cloud secrets
UI — never in code, never committed. A fine-grained token scoped to the single
repository with Contents: read and write is enough; do not use a classic token
with broad `repo` scope if you can avoid it.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

API = "https://api.github.com"
TIMEOUT = 30


class GitHubError(Exception):
    """Any failure talking to the GitHub API, with a readable message."""


@dataclass
class RepoTarget:
    owner: str
    repo: str
    branch: str = "main"
    token: str = ""

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def is_configured(self) -> bool:
        return bool(self.owner and self.repo and self.token)


def _request(target: RepoTarget, method: str, path: str,
             payload: dict | None = None) -> dict:
    url = f"{API}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {target.token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "rmb-3t-intel")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("message", "")
        except Exception:  # noqa: BLE001
            pass
        if exc.code == 401:
            raise GitHubError(
                "GitHub rejected the token (401). It may be expired, mistyped, "
                "or missing Contents write permission."
            ) from exc
        if exc.code == 403:
            raise GitHubError(
                "GitHub refused the request (403). The token likely lacks write "
                "access to this repository, or you have hit a rate limit."
            ) from exc
        if exc.code == 404:
            raise GitHubError(
                f"Repository or branch not found (404): {target.slug} @ "
                f"{target.branch}. Check the owner, repo name and branch, and "
                "that the token can see this repository."
            ) from exc
        if exc.code == 409:
            raise GitHubError(
                "Conflict (409) — the file changed on GitHub since this session "
                "loaded it. Reload the app and redo the change, or commit by hand."
            ) from exc
        raise GitHubError(f"GitHub API error {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"Could not reach GitHub: {exc.reason}") from exc


def check_access(target: RepoTarget) -> dict:
    """Verify the token can see the repo. Returns basic repo info."""
    if not target.is_configured():
        raise GitHubError("GitHub sync is not configured.")
    info = _request(target, "GET", f"/repos/{target.owner}/{target.repo}")
    return {
        "full_name": info.get("full_name"),
        "private": info.get("private"),
        "default_branch": info.get("default_branch"),
        "permissions": info.get("permissions", {}),
    }


def get_sha(target: RepoTarget, path: str) -> str | None:
    """Current blob SHA for a path, or None if the file does not exist yet."""
    try:
        info = _request(
            target, "GET",
            f"/repos/{target.owner}/{target.repo}/contents/{path}"
            f"?ref={target.branch}",
        )
    except GitHubError as exc:
        if "not found" in str(exc).lower() or "404" in str(exc):
            return None
        raise
    if isinstance(info, list):
        raise GitHubError(f"{path} is a directory, not a file.")
    return info.get("sha")


def put_file(target: RepoTarget, path: str, content: bytes,
             message: str) -> dict:
    """Create or update one file. Returns the commit info."""
    if not target.is_configured():
        raise GitHubError("GitHub sync is not configured.")

    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": target.branch,
    }
    sha = get_sha(target, path)
    if sha:
        payload["sha"] = sha

    result = _request(
        target, "PUT",
        f"/repos/{target.owner}/{target.repo}/contents/{path}", payload)
    commit = result.get("commit", {})
    return {
        "path": path,
        "sha": commit.get("sha", "")[:7],
        "url": commit.get("html_url", ""),
        "created": sha is None,
    }


def put_many(target: RepoTarget, files: dict[str, bytes],
             message: str) -> list[dict]:
    """Commit several files, one commit per file (Contents API limitation).

    Stops at the first failure and re-raises, so a partial push is visible
    rather than silent.
    """
    out = []
    for i, (path, content) in enumerate(files.items(), start=1):
        msg = f"{message} ({i}/{len(files)}: {path})"
        out.append(put_file(target, path, content, msg))
    return out
