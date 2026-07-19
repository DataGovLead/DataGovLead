#!/usr/bin/env python3
"""Generate deterministic sections of a GitHub profile README.

The generated content is intentionally driven by profile.json rather than by
unstable third-party profile-card services. Optional remote validation checks
that featured repositories exist and are suitable for public presentation.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
CONFIG_PATH = ROOT / "profile.json"

START_MARKER = "<!-- PROFILE:PROJECTS:START -->"
END_MARKER = "<!-- PROFILE:PROJECTS:END -->"


class ProfileError(RuntimeError):
    """Raised when profile configuration or generation is invalid."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"Missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ProfileError(f"{path} must contain a JSON object.")
    return data


def escape_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").split())


def render_projects(config: dict[str, Any]) -> str:
    username = str(config.get("username", "")).strip()
    projects = config.get("featured_projects")

    if not username:
        raise ProfileError("profile.json must define a non-empty 'username'.")
    if not isinstance(projects, list) or not projects:
        raise ProfileError(
            "profile.json must define at least one item in 'featured_projects'."
        )

    rows = [
        "| Project | Purpose | Stack | Status |",
        "|---|---|---|---|",
    ]

    seen: set[str] = set()
    for index, project in enumerate(projects, start=1):
        if not isinstance(project, dict):
            raise ProfileError(f"featured_projects[{index}] must be an object.")

        repository = str(project.get("repository", "")).strip()
        display_name = str(project.get("display_name", repository)).strip()
        summary = str(project.get("summary", "")).strip()
        status = str(project.get("status", "Active")).strip()
        stack = project.get("stack", [])

        if not repository or not display_name or not summary:
            raise ProfileError(
                f"featured_projects[{index}] requires repository, display_name, "
                "and summary."
            )
        if repository in seen:
            raise ProfileError(f"Duplicate featured repository: {repository}")
        seen.add(repository)

        if not isinstance(stack, list) or not all(
            isinstance(item, str) and item.strip() for item in stack
        ):
            raise ProfileError(
                f"featured_projects[{index}].stack must be a list of strings."
            )

        url = f"https://github.com/{username}/{repository}"
        stack_text = " · ".join(f"`{escape_table_cell(item)}`" for item in stack)
        rows.append(
            "| "
            f"**[{escape_table_cell(display_name)}]({url})** | "
            f"{escape_table_cell(summary)} | "
            f"{stack_text} | "
            f"{escape_table_cell(status)} |"
        )

    return "\n".join(rows)


def replace_generated_section(readme: str, generated: str) -> str:
    if readme.count(START_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise ProfileError(
            "README.md must contain exactly one projects start marker and "
            "one projects end marker."
        )

    before, remainder = readme.split(START_MARKER, maxsplit=1)
    _, after = remainder.split(END_MARKER, maxsplit=1)
    return (
        before
        + START_MARKER
        + "\n"
        + generated.rstrip()
        + "\n"
        + END_MARKER
        + after
    )


def github_get(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "DataGovLead-profile-refresh",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProfileError(f"GitHub API returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise ProfileError(f"Could not reach GitHub API for {url}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ProfileError(f"Unexpected GitHub API response for {url}")
    return payload


def validate_remote(config: dict[str, Any]) -> None:
    username = str(config["username"]).strip()
    token = os.getenv("GITHUB_TOKEN")

    for project in config["featured_projects"]:
        repository = str(project["repository"]).strip()
        metadata = github_get(
            f"https://api.github.com/repos/{username}/{repository}",
            token=token,
        )

        if metadata.get("private"):
            raise ProfileError(f"{username}/{repository} is private.")
        if metadata.get("archived"):
            raise ProfileError(f"{username}/{repository} is archived.")
        if metadata.get("fork") and not bool(project.get("allow_fork", False)):
            raise ProfileError(
                f"{username}/{repository} is a fork. Set allow_fork=true only "
                "when the README labels it accurately."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when README.md is not synchronized with profile.json.",
    )
    parser.add_argument(
        "--validate-remote",
        action="store_true",
        help="Validate featured repositories through the GitHub API.",
    )
    args = parser.parse_args()

    try:
        config = load_json(CONFIG_PATH)
        if args.validate_remote:
            validate_remote(config)

        current = README_PATH.read_text(encoding="utf-8")
        expected = replace_generated_section(current, render_projects(config))

        if args.check:
            if current == expected:
                print("README.md is synchronized with profile.json.")
                return 0

            diff = difflib.unified_diff(
                current.splitlines(),
                expected.splitlines(),
                fromfile="README.md",
                tofile="README.md (expected)",
                lineterm="",
            )
            print("\n".join(diff))
            return 1

        if current == expected:
            print("No generated profile changes.")
            return 0

        README_PATH.write_text(expected, encoding="utf-8")
        print("Updated generated profile sections.")
        return 0

    except (OSError, ProfileError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
