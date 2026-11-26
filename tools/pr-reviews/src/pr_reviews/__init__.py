"""List the GitHub pull requests waiting for your review, and show review karma."""

import sys

from pr_reviews.cli import main as _main


def main() -> None:
    """Run the `pr-reviews` command."""
    sys.exit(_main())
