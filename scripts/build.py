"""Build the workbench from the owner's public GitHub repository metadata."""

import argparse
import base64
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
CATEGORIES = {
    "chrome": ("Chrome 插件", "chrome"),
    "video": ("视频工具", "video"),
    "other": ("其他项目", "catalog"),
}


def fetch_public_repositories(owner):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "song-workbench",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    endpoint = f"https://api.github.com/users/{quote(owner, safe='')}/repos"
    repositories = []
    page = 1
    while True:
        url = f"{endpoint}?type=owner&sort=pushed&direction=desc&per_page=100&page={page}"
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            result = json.load(response)
        if not isinstance(result, list):
            raise ValueError("Expected a public GitHub repository list")
        repositories.extend(result)
        if len(result) < 100:
            return repositories
        page += 1


def parse_timestamp(timestamp):
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def latest_projects(repositories, settings):
    excluded = {name.casefold() for name in settings["exclude"]}
    projects = [
        repo for repo in repositories
        if repo["owner"]["login"].casefold() == settings["owner"].casefold()
        and repo["private"] is False
        and not repo["fork"]
        and not repo["archived"]
        and repo["name"].casefold() not in excluded
        and repo["pushed_at"]
        and parse_timestamp(repo["created_at"]).astimezone(SHANGHAI).year == settings["year"]
    ]
    known_names = {repo["name"].casefold() for repo in projects}
    index = json.loads((ROOT / "data/approved-projects.json").read_text(encoding="utf-8"))
    if index["year"] == settings["year"]:
        for item in index["projects"]:
            name = item["name"]
            if name.casefold() not in known_names:
                projects.append({"name": name, "private": True, "pushed_at": item["pushed_at"]})
                known_names.add(name.casefold())

    earliest = datetime.min.replace(tzinfo=timezone.utc)
    projects.sort(key=lambda repo: repo["name"].casefold())
    projects.sort(
        key=lambda repo: parse_timestamp(repo["pushed_at"]) if repo["pushed_at"] else earliest,
        reverse=True,
    )
    return projects


def project_category(repo, override):
    if "category" in override:
        return override["category"]
    topics = set(repo.get("topics", []))
    if topics & {"chrome-extension", "chrome-extensions", "browser-extension"}:
        return "chrome"
    if topics & {"remotion", "video-editing", "video-tools"}:
        return "video"
    return "other"


def project_icon(filename, glyph):
    if not filename:
        return f'<span class="project-icon glyph glyph-{glyph}" aria-hidden="true"></span>'
    if Path(filename).name != filename or not filename.endswith(".png"):
        raise ValueError(f"Expected a PNG filename in the icon directory: {filename!r}")
    data = (ROOT / "site" / "icons" / filename).read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f'<img class="project-icon" alt="" src="data:image/png;base64,{encoded}">'


def project_card(repo, owner, overrides, featured):
    name = repo["name"]
    config = overrides.get(name, {})
    category = project_category(repo, config)
    category_label, glyph = CATEGORIES[category]
    private = repo.get("private", False)
    icon = project_icon(None if private else config.get("icon"), glyph)
    description = None if private else (config.get("description") or repo.get("description"))
    description_html = f'<p class="project-description">{escape(description)}</p>' if description else ""
    subtitle = None if private else (config.get("label") or repo.get("language"))
    label = f"<span>{escape(subtitle)}</span>" if subtitle else ""

    date_label = "尚无推送"
    if repo["pushed_at"]:
        pushed = parse_timestamp(repo["pushed_at"])
        local_date = pushed.astimezone(SHANGHAI).date().isoformat()
        date_label = f'GitHub 推送于 <time datetime="{escape(pushed.isoformat())}">{local_date}</time>'
    classes = "project featured" if featured else "project"
    badge = '<span class="badge">最新</span>' if featured else ""

    github = f"https://github.com/{quote(owner, safe='')}/{quote(name, safe='')}"
    website = None if private else config.get("website")
    extra_link = ""
    if website and urlsplit(website).scheme == "https" and urlsplit(website).netloc:
        extra_link = f'<a class="card-link" href="{escape(website)}" aria-label="打开 {escape(name)} 在线预览">在线预览</a>'
    github_label = "GitHub" if extra_link else "查看 GitHub"
    visibility = '<span class="visibility">私有</span>' if private else ""
    return f'''        <article class="{classes}" data-category="{category}" aria-labelledby="project-{escape(name)}">
          <div class="card-head">
            {icon}
            <div class="heading-group">
              <h2 id="project-{escape(name)}">{escape(name)}</h2>
              {badge}
              {visibility}
            </div>
          </div>
          {description_html}
          <div class="project-footer">
            <div class="project-meta"><span>{category_label}</span>{label}<span>{date_label}</span></div>
            <div class="actions">
              {extra_link}
              <a class="card-link" href="{escape(github)}" aria-label="在 GitHub 查看 {escape(name)}">{github_label}</a>
            </div>
          </div>
        </article>'''


def build(repositories, settings, refreshed_at):
    projects = latest_projects(repositories, settings)
    cards = "\n".join(
        project_card(repo, settings["owner"], settings["projects"], featured=(index == 0))
        for index, repo in enumerate(projects)
    )
    template = (ROOT / "site" / "index.template.html").read_text(encoding="utf-8")
    page = (
        template.replace("@@YEAR@@", str(settings["year"]))
        .replace("@@SYNC_ISO@@", refreshed_at.isoformat())
        .replace("@@SYNC_LOCAL@@", refreshed_at.astimezone(SHANGHAI).strftime("%Y-%m-%d %H:%M"))
        .replace("@@EMPTY_VISIBILITY@@", "hidden" if projects else "")
        .replace("@@PROJECT_CARDS@@", cards)
    )
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").touch()
    print(f"Generated {len(projects)} projects")
    return projects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos-json", type=Path, help="Use a saved GitHub API response")
    args = parser.parse_args()
    settings = json.loads((ROOT / "workbench.json").read_text(encoding="utf-8"))
    if args.repos_json:
        repositories = json.loads(args.repos_json.read_text(encoding="utf-8"))
    else:
        repositories = fetch_public_repositories(settings["owner"])
    build(repositories, settings, datetime.now(timezone.utc))


if __name__ == "__main__":
    main()
