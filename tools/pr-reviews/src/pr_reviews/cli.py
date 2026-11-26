"""Command-line interface."""

import argparse
import os
import shutil
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pr_reviews import config, github, karma, ranking, render


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
    queue.add_argument(
        "--top",
        type=_non_negative_int,
        metavar="N",
        help="show only the N highest-ranked pull requests; 0 shows all (default: 20)",
    )
    queue.add_argument("--json", action="store_true", help="print JSON")

    karma_ = commands.add_parser(
        "karma",
        help="compare the lines you reviewed with the lines you authored",
        description=(
            "Divide the lines of the pull requests you recently reviewed by the "
            "lines of those you recently authored, newer work weighing more."
        ),
    )
    karma_.add_argument(
        "--config",
        type=Path,
        help=f"configuration file (default: {config.default_path()})",
    )
    karma_.add_argument(
        "--owner",
        action="append",
        default=[],
        metavar="OWNER",
        help="only count repositories of this organization or user; repeatable",
    )
    karma_.add_argument(
        "--exclude-owner",
        action="append",
        default=[],
        metavar="OWNER",
        help="do not count repositories of this organization or user; repeatable",
    )
    karma_.add_argument(
        "--full-weight-days",
        type=_non_negative_float,
        metavar="DAYS",
        help="working days during which work keeps full weight (default: 2)",
    )
    karma_.add_argument(
        "--window-days",
        type=_positive_float,
        metavar="DAYS",
        help="working days after which work no longer counts (default: 10)",
    )
    karma_.add_argument(
        "--target",
        type=_positive_float,
        metavar="KARMA",
        help="the karma you aim for, shown beside the figure",
    )
    karma_.add_argument("--json", action="store_true", help="print JSON")
    return parser


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = 0
    if not number > 0:
        raise argparse.ArgumentTypeError(f"not a positive number: {value}")
    return number


def _non_negative_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        number = -1
    if not number >= 0:
        raise argparse.ArgumentTypeError(f"not a non-negative number: {value}")
    return number


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0:
        raise argparse.ArgumentTypeError(f"not a non-negative integer: {value}")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return the exit status."""
    args = build_parser().parse_args(argv)
    run = _karma if args.command == "karma" else _queue
    try:
        cfg = config.load(
            args.config or config.default_path(), required=args.config is not None
        )
        run(args, cfg)
    except (config.ConfigError, github.GitHubError, karma.WindowError) as e:
        print(f"pr-reviews: {e}", file=sys.stderr)
        return 1
    return 0


def _client() -> github.Client:
    return github.Client(github.http_transport(github.find_token()))


def _warn(client: github.Client) -> None:
    for warning in client.warnings:
        print(f"pr-reviews: warning: {warning}", file=sys.stderr)


def _is_terminal() -> bool:
    return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


def _queue(args: argparse.Namespace, cfg: config.Config) -> None:
    client = _client()
    prs = client.review_requests()
    _warn(client)

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
    top = cfg.top if args.top is None else args.top
    shown = queue[:top] if top else queue
    if args.json:
        print(render.to_json(shown))
    else:
        terminal = _is_terminal()
        print(
            render.to_table(
                shown,
                hidden=len(queue) - len(shown),
                width=shutil.get_terminal_size().columns if terminal else None,
                links=terminal,
                color=terminal and not os.environ.get("NO_COLOR"),
            )
        )


def _karma(args: argparse.Namespace, cfg: config.Config) -> None:
    window = karma.Window(
        full_days=_number(args.full_weight_days, cfg.karma.full_weight_days),
        days=_number(args.window_days, cfg.karma.window_days),
    )
    target = _number(args.target, cfg.karma.target)
    now = datetime.now(UTC)
    since = window.search_since(now)
    client = _client()
    reviewed = client.reviewed_work(since)
    authored = client.authored_work(since)
    _warn(client)
    result = karma.compute(
        reviewed,
        authored,
        now=now,
        tz=None,
        window=window,
        include_owners=[*cfg.include_owners, *args.owner],
        exclude_owners=[*cfg.exclude_owners, *args.exclude_owner],
        ignore=cfg.ignore,
        ignore_by_repo={repo: r.ignore for repo, r in cfg.repos.items()},
    )
    if args.json:
        print(render.karma_to_json(result, target))
    else:
        color = _is_terminal() and not os.environ.get("NO_COLOR")
        print(render.karma_to_text(result, target, color=color))


def _number[T: float | None](flag: float | None, configured: T) -> float | T:
    return configured if flag is None else flag


def _pick(flag: bool | None, configured: bool) -> bool:
    return configured if flag is None else flag
