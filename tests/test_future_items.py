"""Phase 2 (lot 2.4) — a news dated in the future is left out at collection: a feed announced
events months ahead (Finextra), and they would have topped every edition until then."""

from datetime import datetime, timedelta, timezone

from lucidnews.models import ContentItem, SourceType
from lucidnews.pipeline.collect import drop_future_items

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


def item(name: str, published_at: datetime) -> ContentItem:
    return ContentItem(id=name, source_type=SourceType.RSS, title=name, url=f"https://example.org/{name}", published_at=published_at)


def test_news_dated_in_the_future_are_left_out_and_a_time_zone_is_not_the_future() -> None:
    items = [
        item("yesterday", NOW - timedelta(days=1)),
        item("tonight", NOW + timedelta(hours=10)),  # another time zone
        item("webinar", NOW + timedelta(days=3)),
        item("conference", NOW + timedelta(days=90)),
        item("naive", (NOW - timedelta(hours=2)).replace(tzinfo=None)),
    ]
    assert [kept.id for kept in drop_future_items(items, NOW)] == ["yesterday", "tonight", "naive"]
