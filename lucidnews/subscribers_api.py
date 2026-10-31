"""Subscriber preferences for the web app: the write routes of ``lucidnews-api``.

Local-only by design (no accounts yet): the API serves them only when bound to a
loopback address, and every write must come from a same-machine origin (see
``web_api.write_allowed``). Subscribers are addressed by an opaque id derived from
the e-mail, so addresses never appear in URLs or browser history.
"""

from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence

from pydantic import ValidationError

from .i18n import LANGUAGES
from .newsletter.db import SubscriberDB
from .newsletter.models import DetailLevel, DigestPreferences, Frequency, Subscriber, SubscriptionStatus, subscriber_id
from .newsletter.plans import PLAN_LIMITS
from .sectors import DEFAULT_SECTOR, get_sector
from .taxonomy import IMPORTANCE_ORDER

if TYPE_CHECKING:
    from .newsletter.mailer import Mailer

Response = tuple[int, Dict[str, Any]]


def subscriber_payload(subscriber: Subscriber) -> Dict[str, Any]:
    return {
        "id": subscriber_id(subscriber.email),
        "email": subscriber.email,
        "plan": subscriber.plan.value,
        "preferences": subscriber.preferences.model_dump(mode="json"),
        "created_at": subscriber.created_at.isoformat(),
        "status": subscriber.status.value,
        "confirmed_at": subscriber.confirmed_at.isoformat() if subscriber.confirmed_at else None,
        "unsubscribed_at": subscriber.unsubscribed_at.isoformat() if subscriber.unsubscribed_at else None,
    }


def source_options(configured_sources: Mapping[str, str]) -> List[Dict[str, str]]:
    """Values accepted by ``DigestPreferences.sources``: source types, then named sub-sources.

    GitHub user feeds are left out: their items carry the event's repository, not the
    user, so a filter on the user name would never match.
    """
    options: List[Dict[str, str]] = []
    types = sorted(set(configured_sources.values()))
    options.extend({"value": source_type, "type": source_type, "kind": "type"} for source_type in types)
    named: List[Dict[str, str]] = []
    for key, source_type in configured_sources.items():
        prefix = f"{source_type}/"
        if not key.startswith(prefix):
            continue
        name = key.removeprefix(prefix)
        if source_type == "github" and name.startswith("@"):
            continue
        name = name.removeprefix("r/").removeprefix("@")
        named.append({"value": name, "type": source_type, "kind": "source"})
    options.extend(sorted(named, key=lambda option: (option["type"], option["value"].lower())))
    return options


def _validation_errors(exc: ValidationError) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for error in exc.errors():
        key = ".".join(str(part) for part in error["loc"]) or "body"
        fields.setdefault(key, error["msg"].removeprefix("Value error, "))
    return fields


class SubscriberService:
    def __init__(
        self,
        store: SubscriberDB,
        languages: Sequence[str],
        configured_sources: Mapping[str, str],
        weekly_day: int = 0,
        mailer: Optional[Callable[[], Optional["Mailer"]]] = None,
        categories: Optional[Sequence[str]] = None,
    ):
        self.store = store
        # The installation's sector decides which domains a subscriber can choose.
        self.categories = list(categories) if categories is not None else get_sector(DEFAULT_SECTOR).category_ids
        self.weekly_day = weekly_day
        # Built per request so a key added in Settings is used without restarting the API.
        self._mailer = mailer or (lambda: None)
        self.languages = [code for code in languages if code in LANGUAGES] or ["en"]
        self.configured_sources = dict(configured_sources)

    def options(self) -> Dict[str, Any]:
        return {
            "languages": [
                {"code": code, "name": LANGUAGES[code].native_name} for code in self.languages
            ],
            "categories": list(self.categories),
            "frequencies": [frequency.value for frequency in Frequency],
            "detail_levels": [level.value for level in DetailLevel],
            "weekly_day": self.weekly_day,
            "importance_levels": [level.value for level in IMPORTANCE_ORDER],
            "sources": source_options(self.configured_sources),
            # Both plans are unlimited until the product is validated: shown, never billed.
            "plans": [
                {
                    "id": plan.value,
                    "max_categories": limits.max_categories,
                    "max_sources": limits.max_sources,
                    "max_items": limits.max_items,
                }
                for plan, limits in PLAN_LIMITS.items()
            ],
        }

    def _language_error(self, preferences: DigestPreferences) -> Optional[Response]:
        if preferences.language in self.languages:
            return None
        return HTTPStatus.UNPROCESSABLE_ENTITY, {
            "error": "invalid preferences",
            "fields": {"language": f"not produced by this instance (available: {', '.join(self.languages)})"},
        }

    def list(self) -> Response:
        subscribers = sorted(self.store.load(), key=lambda s: s.created_at)
        return HTTPStatus.OK, {"subscribers": [subscriber_payload(s) for s in subscribers]}

    def get(self, sub_id: str) -> Optional[Subscriber]:
        return self.store.get_by_id(sub_id)

    def _confirmation(self, subscriber: Subscriber) -> Dict[str, Any]:
        """Send the confirmation link; the subscriber stays pending whatever happens."""
        mailer = self._mailer()
        if mailer is None:
            return {"sent": False, "error": "e-mail sending is not enabled (email.enabled)"}
        result = mailer.send_confirmation(subscriber)
        return {"sent": result.ok, "error": result.error}

    def create(self, body: Mapping[str, Any]) -> Response:
        try:
            preferences = DigestPreferences.model_validate(
                body.get("preferences") or {"language": self.languages[0]}
            )
            # Pending: nothing is sent to this address until its owner opens the confirmation link.
            subscriber = Subscriber(
                email=str(body.get("email", "")), preferences=preferences, status=SubscriptionStatus.PENDING
            )
        except ValidationError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid subscriber", "fields": _validation_errors(exc)}
        if error := self._language_error(preferences):
            return error
        if not self.store.insert(subscriber):
            return HTTPStatus.CONFLICT, {"error": "subscriber already exists", "fields": {"email": "already subscribed"}}
        return HTTPStatus.CREATED, {**subscriber_payload(subscriber), "confirmation": self._confirmation(subscriber)}

    def resend_confirmation(self, sub_id: str) -> Response:
        subscriber = self.store.get_by_id(sub_id)
        if subscriber is None:
            return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
        if subscriber.status is SubscriptionStatus.UNSUBSCRIBED:
            # A reader who left comes back only by asking again: back to pending, then the link.
            subscriber = self.store.request_again(sub_id) or subscriber
        if subscriber.status is not SubscriptionStatus.PENDING:
            return HTTPStatus.CONFLICT, {"error": "subscriber is not waiting for confirmation"}
        return HTTPStatus.OK, {**subscriber_payload(subscriber), "confirmation": self._confirmation(subscriber)}

    def update(self, sub_id: str, body: Mapping[str, Any]) -> Response:
        try:
            preferences = DigestPreferences.model_validate(body.get("preferences"))
        except ValidationError as exc:
            return HTTPStatus.UNPROCESSABLE_ENTITY, {"error": "invalid preferences", "fields": _validation_errors(exc)}
        if error := self._language_error(preferences):
            return error
        # The plan is display-only: no billing, so the web app cannot change it.
        if not self.store.set_preferences(sub_id, preferences):
            return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
        return HTTPStatus.OK, subscriber_payload(self.store.get_by_id(sub_id))

    def delete(self, sub_id: str) -> Response:
        # Erasing removes everything, including the delivery log; nothing is kept.
        if not self.store.delete(sub_id):
            return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
        return HTTPStatus.OK, {"deleted": sub_id}

    def deliveries(self, sub_id: Optional[str], limit: int) -> Response:
        if sub_id is not None and self.store.get_by_id(sub_id) is None:
            return HTTPStatus.NOT_FOUND, {"error": "subscriber not found"}
        return HTTPStatus.OK, {"deliveries": [d.to_dict() for d in self.store.deliveries(subscriber=sub_id, limit=limit)]}
