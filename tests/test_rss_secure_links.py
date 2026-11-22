"""Phase 3 (lot 3.4) — an http link to the site of an https feed becomes https; others stay."""

from lucidnews.scrapers.rss import secure_link

FEED = "https://www.senat.fr/rss/textes.rss"


def test_a_link_to_the_feeds_own_site_is_served_over_https() -> None:
    assert secure_link("http://www.senat.fr/leg/pjl26-187.html", FEED) == "https://www.senat.fr/leg/pjl26-187.html"


def test_links_elsewhere_or_from_an_http_feed_are_left_as_written() -> None:
    assert secure_link("http://ailleurs.example/x", FEED) == "http://ailleurs.example/x"
    assert secure_link("http://senat.fr/x", FEED) == "http://senat.fr/x"  # another host name
    assert secure_link("http://www.senat.fr/x", "http://www.senat.fr/rss") == "http://www.senat.fr/x"
    assert secure_link("https://www.senat.fr/x", FEED) == "https://www.senat.fr/x"
