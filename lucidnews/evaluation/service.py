"""Evaluation data for the web app and the CLI: candidates to annotate, annotations, report."""

import hashlib
import html
import re
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, Mapping, Optional, Sequence

from pydantic import ValidationError

from ..archive import ItemArchive
from ..models import Config, ContentItem
from ..reliability import ReliabilityLabel
from ..reliability.assess import ReliabilityPolicy
from .metrics import SelectionRule, evaluate, pipeline_selection_rule
from .models import Annotation
from .store import AnnotationStore

Response = tuple[int, Dict[str, Any]]

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
EXCERPT_CHARS = 700
COMMENTS_MARKER = "--- Top Comments ---"


def excerpt(item: ContentItem) -> str:
    """Plain-text start of the collected content (what a reader would see), never AI output."""
    text = item.content or ""
    body, _, comments = text.partition(COMMENTS_MARKER)
    text = body if body.strip() else comments
    text = _SPACE.sub(" ", html.unescape(_TAG.sub(" ", text))).strip()
    return text[:EXCERPT_CHARS] + ("…" if len(text) > EXCERPT_CHARS else "")


def _source_label(item: ContentItem) -> str:
    for key in ("feed_name", "repo", "subreddit", "channel"):
        if item.metadata.get(key):
            return str(item.metadata[key])
    return item.source_type.value


def _shuffle_key(item_id: str) -> str:
    # Stable pseudo-random order: annotators do not see items sorted by AI score.
    return hashlib.sha256(item_id.encode("utf-8")).hexdigest()


def _errors(exc: ValidationError) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for error in exc.errors():
        key = ".".join(str(part) for part in error["loc"]) or "body"
        fields.setdefault(key, error["msg"].removeprefix("Value error, "))
    return fields


class EvaluationService:
    def __init__(
        self,
        archive: ItemArchive,
        store: AnnotationStore,
        selection_rule: SelectionRule,
        policy: Optional[ReliabilityPolicy] = None,
    ):
        self.archive = archive
        self.store = store
        self.selection_rule = selection_rule
        self.policy = policy or ReliabilityPolicy()

    @classmethod
    def from_config(cls, config: Config, archive: ItemArchive, store: AnnotationStore) -> "EvaluationService":
        thresholds = {
            profile: settings.threshold for profile, settings in config.processing.profile_settings.items()
        }
        exclude: Sequence[ReliabilityLabel] = config.reliability.exclude_labels if config.reliability else ()
        policy = ReliabilityPolicy.for_config(config)
        return cls(archive, store, pipeline_selection_rule(thresholds, exclude), policy)

    def analyzed_items(self) -> Dict[str, ContentItem]:
        items = self.archive.items_between(datetime(1970, 1, 1, tzinfo=timezone.utc))
        return {
            item.id: item
            for item in items
            if item.processing and item.processing.analysis and item.processing.analysis.score is not None
        }

    def candidates(self) -> Dict[str, Any]:
        """Items to annotate, blind: no score, summary, category or label from the AI."""
        annotations = self.store.load()
        items = sorted(self.analyzed_items().values(), key=lambda item: _shuffle_key(item.id))
        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "url": str(item.url),
                    "source_type": item.source_type.value,
                    "source": _source_label(item),
                    "author": item.author,
                    "published_at": item.published_at.isoformat(),
                    "excerpt": excerpt(item),
                    "discussion_url": item.metadata.get("discussion_url"),
                    "annotation": (
                        annotations[item.id].model_dump(mode="json") if item.id in annotations else None
                    ),
                }
                for item in items
            ],
            "annotated": sum(1 for item in items if item.id in annotations),
        }

    def annotate(self, item_id: str, body: Mapping[str, Any]) -> Response:
        item = self.archive.get_item(item_id)
        if item is None:
            return HTTPStatus.NOT_FOUND, {"error": "item not found"}
        try:
            annotation = Annotation.model_validate(
                {**body, "item_id": item_id, "title": item.title, "url": str(item.url)}
            )
        except ValidationError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid annotation", "fields": _errors(exc)}
        return HTTPStatus.OK, self.store.upsert(annotation).model_dump(mode="json")

    def unannotate(self, item_id: str) -> Response:
        if not self.store.delete(item_id):
            return HTTPStatus.NOT_FOUND, {"error": "annotation not found"}
        return HTTPStatus.OK, {"deleted": item_id}

    def report(self, items: Optional[Mapping[str, ContentItem]] = None) -> Dict[str, Any]:
        annotations = self.store.load()
        if items is None:
            items = self.archive.get_items(list(annotations))
        return evaluate(annotations, items, self.selection_rule, self.policy).to_dict()

