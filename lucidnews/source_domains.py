"""The domain (taxonomy category) of each configured source.

Two real signals, never a guess:

- **archive**: the categories the AI gave to the analyzed items the source produced;
  the domain is the most frequent one, and the first few are listed with their counts;
- **catalog**: for a source with no analyzed item yet, the category the curated catalog
  (``data/config.example.json``, setup presets) gives it, when it lists that source.

A source with neither has no domain: the interface says so.
"""

from collections import Counter
from typing import Dict, Iterable, List, Optional, Sequence

from .models import ContentItem
from .source_catalog import CatalogEntry
from .source_quality import item_source_key
from .sectors import all_categories

TOP_CATEGORIES = 3
_ORDER = {category.id: index for index, category in enumerate(all_categories())}


def source_domains(
    items: Iterable[ContentItem], catalog: Sequence[CatalogEntry], source_keys: Iterable[str]
) -> Dict[str, Dict[str, object]]:
    counts: Dict[str, Counter] = {}
    for item in items:
        analysis = item.processing.analysis if item.processing else None
        if analysis is None or analysis.score is None or not analysis.categories:
            continue
        counts.setdefault(item_source_key(item), Counter()).update(analysis.categories)
    declared = {entry.key: entry.category for entry in catalog}

    result: Dict[str, Dict[str, object]] = {}
    for key in source_keys:
        counter = counts.get(key)
        if counter:
            ranked = sorted(counter.items(), key=lambda pair: (-pair[1], _ORDER.get(pair[0], 99)))
            result[key] = {
                "category": ranked[0][0],
                "origin": "archive",
                "categories": [{"category": name, "items": count} for name, count in ranked[:TOP_CATEGORIES]],
            }
        elif key in declared:
            result[key] = {"category": declared[key], "origin": "catalog", "categories": []}
        else:
            result[key] = {"category": None, "origin": None, "categories": []}
    return result
