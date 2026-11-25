"""Command-line interface."""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pr_reviews import config, github, ranking, render


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pr-reviews", description="Work through GitHub review requests."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser(
        "queue",
        help="list the pull requests waiting for your review, ranked",
        description=(
            "List the open, non-draft pull requests on GitHub.com that request "
            "your review, overdue ones first, then by priority."
        ),
    )
    queue.add_argument(
        "--config",
        type=Path,
        help=f"configuration file (default: {config.default_path()})",
    )
    queue.add_argument(
        "--owner",
        action="append",
        default=[],
        metavar="OWNER",
        help="only include repositories of this organization or user; repeatable",
    )
    queue.add_argument(
        "--exclude-owner",
        action="append",
        default=[],
        metavar="OWNER",
        help="exclude repositories of this organization or user; repeatable",
    )
    queue.add_argument(
        "--direct-only",
        action="store_true",
        default=None,
        help="only include requests made to you directly, not through a team",
    )
    queue.add_argument(
        "--hide-approved",
        action="store_true",
        default=None,
        help="hide pull requests that GitHub reports as approved",
    )
    queue.add_argument(
        "--limit-days",
        type=_positive_float,
        metavar="DAYS",
        help="working days after which a pull request is overdue",
    )
    queue.add_argument("--json", action="store_true", help="print JSON")
    return parser


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0
    if not number > 0:
        raise argparse.ArgumentTypeError(f"not a positive number: {value}")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit status."""
    args = build_parser().parse_args(argv)
    try:
        cfg = config.load(
            args.config or config.default_path(), required=args.config is not None
        )
        client = github.Client(github.http_transport(github.find_token()))
        prs = client.review_requests()
    except (config.ConfigError, github.GitHubError) as e:
        print(f"pr-reviews: {e}", file=sys.stderr)
        return 1
    for warning in client.warnings:
        print(f"pr-reviews: warning: {warning}", file=sys.stderr)

    selected = ranking.select(
        prs,
        include_owners=[*cfg.include_owners, *args.owner],
        exclude_owners=[*cfg.exclude_owners, *args.exclude_owner],
        direct_only=_pick(args.direct_only, cfg.direct_only),
        hide_approved=_pick(args.hide_approved, cfg.hide_approved),
    )
    queue = ranking.rank(
        selected,
        now=datetime.now(UTC),
        tz=None,
        limit_days=args.limit_days or cfg.limit_days,
        ignore=cfg.ignore,
        ignore_by_repo={repo: r.ignore for repo, r in cfg.repos.items()},
    )
    if args.json:
        print(render.to_json(queue))
    else:
        links = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"
        print(render.to_table(queue, links=links))
    return 0


def _pick(flag: bool | None, configured: bool) -> bool:
    return configured if flag is None else flag
