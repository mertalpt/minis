"""Read review requests from the GitHub.com GraphQL API."""

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pr_reviews.ranking import ChangedFile, PullRequest, Request

API_URL = "https://api.github.com/graphql"
SEARCH_ALL = "is:pr is:open draft:false archived:false review-requested:@me"
SEARCH_DIRECT = "is:pr is:open draft:false archived:false user-review-requested:@me"

Transport = Callable[[str, dict[str, Any]], dict[str, Any]]
"""Sends a GraphQL query with variables and returns the response body."""


class GitHubError(Exception):
    """A request to GitHub failed."""


class CredentialsError(GitHubError):
    """GitHub credentials are missing or rejected."""


def find_token() -> str:
    """Return the user's GitHub token.

    Reads `GH_TOKEN`, then `GITHUB_TOKEN`, then asks `gh auth token`.

    Raises:
        CredentialsError: No token was found.
    """
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if token := os.environ.get(name, "").strip():
            return token
    gh = shutil.which("gh")
    if gh is not None:
        result = subprocess.run(
            [gh, "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and (token := result.stdout.strip()):
            return token
    raise CredentialsError(
        "no GitHub credentials: set GH_TOKEN or GITHUB_TOKEN, or run `gh auth login`"
    )


def http_transport(token: str) -> Transport:
    """Return a transport that posts to the GitHub.com GraphQL API."""

    def post(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            API_URL,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Authorization": f"bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "pr-reviews",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body: dict[str, Any] = json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise CredentialsError(
                    "GitHub rejected the credentials (HTTP 401)"
                ) from None
            raise GitHubError(f"GitHub returned HTTP {e.code} {e.reason}") from None
        except urllib.error.URLError as e:
            raise GitHubError(f"cannot reach GitHub: {e.reason}") from None
        return body

    return post


_FILES = "pageInfo { hasNextPage endCursor } nodes { path additions deletions }"

SEARCH_QUERY = f"""
query($q: String!, $after: String) {{
  search(query: $q, type: ISSUE, first: 50, after: $after) {{
    pageInfo {{ hasNextPage endCursor }}
    nodes {{
      ... on PullRequest {{
        id number title url createdAt additions deletions reviewDecision
        repository {{ name owner {{ login }} }}
        timelineItems(itemTypes: [READY_FOR_REVIEW_EVENT], last: 1) {{
          nodes {{ ... on ReadyForReviewEvent {{ createdAt }} }}
        }}
        files(first: 100) {{ {_FILES} }}
      }}
    }}
  }}
}}
"""

SEARCH_IDS_QUERY = """
query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest { id } }
  }
}
"""

FILES_QUERY = f"""
query($id: ID!, $after: String) {{
  node(id: $id) {{
    ... on PullRequest {{ files(first: 100, after: $after) {{ {_FILES} }} }}
  }}
}}
"""


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class _PageInfo(_Model):
    has_next_page: bool = Field(alias="hasNextPage")
    end_cursor: str | None = Field(alias="endCursor")


class _File(_Model):
    path: str
    additions: int
    deletions: int


class _Files(_Model):
    page_info: _PageInfo = Field(alias="pageInfo")
    nodes: list[_File | None]


class _Owner(_Model):
    login: str


class _Repository(_Model):
    name: str
    owner: _Owner


class _ReadyEvent(_Model):
    created_at: datetime = Field(alias="createdAt")


class _Timeline(_Model):
    nodes: list[_ReadyEvent | None]


class _PullRequest(_Model):
    id: str
    number: int
    title: str
    url: str
    created_at: datetime = Field(alias="createdAt")
    additions: int
    deletions: int
    review_decision: (
        Literal["APPROVED", "REVIEW_REQUIRED", "CHANGES_REQUESTED"] | None
    ) = Field(alias="reviewDecision")
    repository: _Repository
    timeline_items: _Timeline = Field(alias="timelineItems")
    files: _Files | None


class _Search(_Model):
    page_info: _PageInfo = Field(alias="pageInfo")
    # Search returns other kinds of nodes as empty objects, and nodes the
    # credentials cannot read as null.
    nodes: list[dict[str, Any] | None]


class _SearchData(_Model):
    search: _Search


class _FilesNode(_Model):
    files: _Files | None = None


class _FilesData(_Model):
    node: _FilesNode | None


class Client:
    """Reads the review requests visible to the user's credentials."""

    def __init__(self, transport: Transport) -> None:
        """Create a client that sends queries through a transport."""
        self._transport = transport
        self.warnings: list[str] = []

    def review_requests(self) -> list[PullRequest]:
        """Return the open, non-draft pull requests requesting the user's review.

        Raises:
            GitHubError: A request failed.
        """
        direct = {node["id"] for node in self._search(SEARCH_IDS_QUERY, SEARCH_DIRECT)}
        prs = []
        for raw in self._search(SEARCH_QUERY, SEARCH_ALL):
            node = _validate(_PullRequest, raw)
            request = Request.DIRECT if node.id in direct else Request.TEAM
            prs.append(self._convert(node, request))
        return prs

    def _search(self, query: str, q: str) -> Iterator[dict[str, Any]]:
        after: str | None = None
        while True:
            data = self._query(query, {"q": q, "after": after}, _SearchData)
            yield from (node for node in data.search.nodes if node and "id" in node)
            if not data.search.page_info.has_next_page:
                return
            after = data.search.page_info.end_cursor

    def _convert(self, node: _PullRequest, request: Request) -> PullRequest:
        ready = [e.created_at for e in node.timeline_items.nodes if e is not None]
        return PullRequest(
            owner=node.repository.owner.login,
            repo=node.repository.name,
            number=node.number,
            title=node.title,
            url=node.url,
            ready_at=ready[-1] if ready else node.created_at,
            additions=node.additions,
            deletions=node.deletions,
            files=tuple(self._files(node)),
            approved=node.review_decision == "APPROVED",
            request=request,
        )

    def _files(self, node: _PullRequest) -> Iterator[ChangedFile]:
        files = node.files
        while files is not None:
            for f in files.nodes:
                if f is not None:
                    yield ChangedFile(f.path, f.additions, f.deletions)
            if not files.page_info.has_next_page:
                return
            data = self._query(
                FILES_QUERY,
                {"id": node.id, "after": files.page_info.end_cursor},
                _FilesData,
            )
            files = data.node.files if data.node is not None else None

    def _query[M: BaseModel](
        self, query: str, variables: dict[str, Any], model: type[M]
    ) -> M:
        body = self._transport(query, variables)
        errors = body.get("errors") or []
        messages = [str(e.get("message", e)) for e in errors if isinstance(e, dict)]
        if body.get("data") is None:
            raise GitHubError("GitHub query failed: " + "; ".join(messages))
        # Partial data comes with errors for what the credentials cannot
        # read, such as organizations that enforce SAML single sign-on.
        self.warnings.extend(m for m in messages if m not in self.warnings)
        return _validate(model, body["data"])


def _validate[M: BaseModel](model: type[M], data: object) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise GitHubError(f"unexpected response from GitHub: {e}") from None
