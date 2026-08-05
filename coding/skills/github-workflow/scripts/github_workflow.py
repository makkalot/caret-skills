#!/usr/bin/env python3
import argparse
import getpass
import io
import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


API = "https://api.github.com"
TOKEN_DIR = Path(".caret/github-workflow/tokens")


class GitHubError(Exception):
    pass


def actor_key():
    adapter = os.environ.get("CARET_ADAPTER", "").strip()
    user_id = os.environ.get("CARET_USER_ID", "").strip()
    if not adapter or not user_id:
        raise GitHubError("missing Caret actor identity: CARET_ADAPTER and CARET_USER_ID are required")
    safe_adapter = "".join(c for c in adapter if c.isalnum() or c in ("-", "_"))
    safe_user = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
    if not safe_adapter or not safe_user:
        raise GitHubError("invalid Caret actor identity")
    return f"{safe_adapter}-{safe_user}"


def token_path():
    return TOKEN_DIR / (actor_key() + ".token")


def read_token(args=None, required=True):
    if args is not None:
        token = getattr(args, "token", None)
        if token:
            return token.strip()
        token_env = getattr(args, "token_env", None)
        if token_env:
            token = os.environ.get(token_env, "").strip()
            if token:
                return token
            raise GitHubError(f"environment variable {token_env} is empty")
    try:
        path = token_path()
    except GitHubError:
        if required:
            raise
        return ""
    if path.exists():
        return path.read_text().strip()
    if required:
        raise GitHubError("missing GitHub token: run auth set-token first")
    return ""


def store_token(token):
    token = token.strip()
    if not token:
        raise GitHubError("token is empty")
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    path = token_path()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    return path


def request_json(method, path, token, payload=None, accept="application/vnd.github+json"):
    data = None
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "caret-github-workflow",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        message = body
        try:
            decoded = json.loads(body)
            message = decoded.get("message", body)
        except json.JSONDecodeError:
            pass
        raise GitHubError(f"HTTP {e.code}: {message}") from None
    except urllib.error.URLError as e:
        raise GitHubError(f"network error: {e.reason}") from None


def request_bytes(method, path, token, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "caret-github-workflow",
        "Authorization": "Bearer " + token,
    }
    req = urllib.request.Request(API + path, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise GitHubError(f"HTTP {e.code}: {body}") from None
    except urllib.error.URLError as e:
        raise GitHubError(f"network error: {e.reason}") from None


def repo_path(repo, suffix):
    if "/" not in repo or repo.count("/") != 1:
        raise GitHubError("repo must be owner/repo")
    owner, name = [urllib.parse.quote(part, safe="") for part in repo.split("/", 1)]
    return f"/repos/{owner}/{name}{suffix}"


def looks_like_sha(value):
    value = value.strip().lower()
    return len(value) in (40, 64) and all(c in "0123456789abcdef" for c in value)


def print_json(value):
    print(json.dumps(value, indent=2, sort_keys=True))


def cmd_auth_status(args):
    token = read_token(args, required=False)
    if not token:
        print("No token stored for current Caret user.")
        return
    user = request_json("GET", "/user", token)
    print(f"Authenticated as {user.get('login', 'unknown')}.")


def cmd_auth_set_token(args):
    token = args.token or ""
    if args.token_env:
        token = os.environ.get(args.token_env, "")
    if args.token_stdin:
        token = sys.stdin.read()
    if not token and sys.stdin.isatty():
        token = getpass.getpass("GitHub token: ")
    store_token(token)
    user = request_json("GET", "/user", token)
    print(f"Stored token for current Caret user. Authenticated as {user.get('login', 'unknown')}.")


def cmd_pr_view(args):
    token = read_token(args)
    pr = request_json("GET", repo_path(args.repo, f"/pulls/{args.number}"), token)
    if args.raw:
        print_json(pr)
        return
    print(f"PR #{pr['number']}: {pr['title']}")
    print(f"State: {pr['state']}  Draft: {pr.get('draft', False)}  Author: {pr.get('user', {}).get('login', 'unknown')}")
    print(f"Head: {pr.get('head', {}).get('label')}  Base: {pr.get('base', {}).get('label')}")
    print(f"SHA: {pr.get('head', {}).get('sha', '')}")
    print(f"URL: {pr.get('html_url', '')}")
    if pr.get("body"):
        print("\nBody:\n" + pr["body"][:4000])


def cmd_pr_create(args):
    token = read_token(args)
    payload = {
        "title": args.title,
        "head": args.head,
        "base": args.base,
        "body": args.body or "",
        "draft": bool(args.draft),
    }
    pr = request_json("POST", repo_path(args.repo, "/pulls"), token, payload)
    if args.raw:
        print_json(pr)
        return
    print(f"Created PR #{pr['number']}: {pr.get('html_url', '')}")


def cmd_pr_comments(args):
    token = read_token(args)
    issue_comments = request_json("GET", repo_path(args.repo, f"/issues/{args.number}/comments?per_page=100"), token)
    review_comments = request_json("GET", repo_path(args.repo, f"/pulls/{args.number}/comments?per_page=100"), token)
    result = {"issue_comments": issue_comments, "review_comments": review_comments}
    if args.raw:
        print_json(result)
        return
    print(f"Issue comments: {len(issue_comments)}")
    for comment in issue_comments:
        print(f"- {comment.get('user', {}).get('login', 'unknown')}: {comment.get('body', '').strip()[:500]}")
    print(f"\nReview comments: {len(review_comments)}")
    for comment in review_comments:
        where = comment.get("path", "")
        if comment.get("line"):
            where += f":{comment['line']}"
        print(f"- {comment.get('user', {}).get('login', 'unknown')} {where}: {comment.get('body', '').strip()[:500]}")


def cmd_checks_list(args):
    token = read_token(args)
    query = {"per_page": "100"}
    if args.ref:
        if looks_like_sha(args.ref):
            query["head_sha"] = args.ref
        else:
            query["branch"] = args.ref
    query_string = urllib.parse.urlencode(query)
    runs = request_json("GET", repo_path(args.repo, f"/actions/runs?{query_string}"), token)
    if args.raw:
        print_json(runs)
        return
    items = runs.get("workflow_runs", [])
    target = args.ref or "latest runs"
    print(f"Workflow runs for {target}: {len(items)}")
    for run in items:
        conclusion = run.get("conclusion") or run.get("status")
        head = run.get("head_branch") or run.get("head_sha", "")
        print(f"- {run.get('name')} [{conclusion}] run_id={run.get('id')} branch={head} url={run.get('html_url', '')}")


def cmd_checks_logs(args):
    token = read_token(args)
    data, _ = request_bytes("GET", repo_path(args.repo, f"/actions/runs/{args.run_id}/logs"), token)
    if args.raw:
        sys.stdout.buffer.write(data)
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        print(data.decode("utf-8", errors="replace")[:20000])
        return
    printed = 0
    for name in zf.namelist():
        if printed >= args.max_files:
            remaining = len(zf.namelist()) - printed
            if remaining > 0:
                print(f"\n... {remaining} log files omitted ...")
            break
        with zf.open(name) as f:
            content = f.read(args.max_bytes).decode("utf-8", errors="replace")
        print(f"\n===== {name} =====")
        print(content)
        printed += 1


def cmd_comment_create(args):
    token = read_token(args)
    payload = {"body": args.body}
    comment = request_json("POST", repo_path(args.repo, f"/issues/{args.issue_or_pr}/comments"), token, payload)
    if args.raw:
        print_json(comment)
        return
    print(f"Created comment: {comment.get('html_url', '')}")


def add_token_args(parser):
    parser.add_argument("--token", help=argparse.SUPPRESS)
    parser.add_argument("--token-env", help="Read a one-off token from this environment variable")


def build_parser():
    parser = argparse.ArgumentParser(description="Caret GitHub workflow helper")
    sub = parser.add_subparsers(dest="group", required=True)

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="command", required=True)
    auth_status = auth_sub.add_parser("status")
    add_token_args(auth_status)
    auth_status.set_defaults(func=cmd_auth_status)
    auth_set = auth_sub.add_parser("set-token")
    auth_set.add_argument("--token", help=argparse.SUPPRESS)
    auth_set.add_argument("--token-env", help="Read token from this environment variable")
    auth_set.add_argument("--token-stdin", action="store_true", help="Read token from stdin")
    auth_set.set_defaults(func=cmd_auth_set_token)

    pr = sub.add_parser("pr")
    pr_sub = pr.add_subparsers(dest="command", required=True)
    pr_view = pr_sub.add_parser("view")
    add_token_args(pr_view)
    pr_view.add_argument("--repo", required=True)
    pr_view.add_argument("--number", required=True, type=int)
    pr_view.add_argument("--raw", action="store_true")
    pr_view.set_defaults(func=cmd_pr_view)
    pr_create = pr_sub.add_parser("create")
    add_token_args(pr_create)
    pr_create.add_argument("--repo", required=True)
    pr_create.add_argument("--head", required=True)
    pr_create.add_argument("--base", required=True)
    pr_create.add_argument("--title", required=True)
    pr_create.add_argument("--body", default="")
    pr_create.add_argument("--draft", action="store_true")
    pr_create.add_argument("--raw", action="store_true")
    pr_create.set_defaults(func=cmd_pr_create)
    pr_comments = pr_sub.add_parser("comments")
    add_token_args(pr_comments)
    pr_comments.add_argument("--repo", required=True)
    pr_comments.add_argument("--number", required=True, type=int)
    pr_comments.add_argument("--raw", action="store_true")
    pr_comments.set_defaults(func=cmd_pr_comments)

    checks = sub.add_parser("checks")
    checks_sub = checks.add_subparsers(dest="command", required=True)
    checks_list = checks_sub.add_parser("list")
    add_token_args(checks_list)
    checks_list.add_argument("--repo", required=True)
    checks_list.add_argument("--ref", required=True)
    checks_list.add_argument("--raw", action="store_true")
    checks_list.set_defaults(func=cmd_checks_list)
    checks_logs = checks_sub.add_parser("logs")
    add_token_args(checks_logs)
    checks_logs.add_argument("--repo", required=True)
    checks_logs.add_argument("--run-id", required=True)
    checks_logs.add_argument("--raw", action="store_true")
    checks_logs.add_argument("--max-files", type=int, default=20)
    checks_logs.add_argument("--max-bytes", type=int, default=20000)
    checks_logs.set_defaults(func=cmd_checks_logs)

    comment = sub.add_parser("comment")
    comment_sub = comment.add_subparsers(dest="command", required=True)
    comment_create = comment_sub.add_parser("create")
    add_token_args(comment_create)
    comment_create.add_argument("--repo", required=True)
    comment_create.add_argument("--issue-or-pr", required=True, type=int)
    comment_create.add_argument("--body", required=True)
    comment_create.add_argument("--raw", action="store_true")
    comment_create.set_defaults(func=cmd_comment_create)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except GitHubError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
