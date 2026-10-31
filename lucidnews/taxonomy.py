"""Product taxonomy: IT news categories and importance levels.

Categories are assigned by the AI analysis stage (see ``ai/prompting/analysis.py``)
and used for newsletter preferences and digest selection. They are independent of
the free-form ``category`` label on a source config, which only drives digest quotas.
"""

from enum import Enum
from typing import Dict, Iterable, List, Optional


class Category(str, Enum):
    """Top-level IT categories covered by LucidNews."""

    AI = "ai"
    SOFTWARE_DEVELOPMENT = "software-development"
    CLOUD = "cloud"
    DEVOPS = "devops"
    DATA = "data"
    CYBERSECURITY = "cybersecurity"
    WEB = "web"
    OPEN_SOURCE = "open-source"
    DEVELOPER_TOOLS = "developer-tools"
    DATABASES = "databases"
    INFRASTRUCTURE = "infrastructure"
    EMERGING_TECH = "emerging-tech"


CATEGORY_LABELS: dict[Category, dict[str, str]] = {
    Category.AI: {"en": "AI / LLM / Agents", "fr": "IA / LLM / Agents"},
    Category.SOFTWARE_DEVELOPMENT: {"en": "Software Development", "fr": "Développement logiciel"},
    Category.CLOUD: {"en": "Cloud", "fr": "Cloud"},
    Category.DEVOPS: {"en": "DevOps", "fr": "DevOps"},
    Category.DATA: {"en": "Data", "fr": "Data"},
    Category.CYBERSECURITY: {"en": "Cybersecurity", "fr": "Cybersécurité"},
    Category.WEB: {"en": "Web", "fr": "Web"},
    Category.OPEN_SOURCE: {"en": "Open Source", "fr": "Open Source"},
    Category.DEVELOPER_TOOLS: {"en": "Developer Tools", "fr": "Outils développeurs"},
    Category.DATABASES: {"en": "Databases", "fr": "Bases de données"},
    Category.INFRASTRUCTURE: {"en": "Infrastructure", "fr": "Infrastructure"},
    Category.EMERGING_TECH: {"en": "Emerging Technologies", "fr": "Technologies émergentes"},
}

# One-line scope used in AI prompts so the model assigns categories consistently.
CATEGORY_SCOPES: dict[Category, str] = {
    Category.AI: "models, LLMs, agents, ML research and AI products",
    Category.SOFTWARE_DEVELOPMENT: "languages, frameworks, architecture and engineering practice",
    Category.CLOUD: "cloud providers, managed services, serverless and pricing",
    Category.DEVOPS: "CI/CD, containers, Kubernetes, observability and SRE",
    Category.DATA: "data engineering, analytics, pipelines and data platforms",
    Category.CYBERSECURITY: "vulnerabilities, breaches, threats, security tooling and policy",
    Category.WEB: "browsers, web standards, frontend and web platforms",
    Category.OPEN_SOURCE: "open-source projects, licensing, foundations and maintainers",
    Category.DEVELOPER_TOOLS: "IDEs, compilers, linkers, build systems and developer workflow",
    Category.DATABASES: "database engines, storage engines and query systems",
    Category.INFRASTRUCTURE: "hardware, chips, operating systems, networking and data centers",
    Category.EMERGING_TECH: "quantum, robotics, AR/VR, biotech-computing and other frontier tech",
}

_ALIASES: dict[str, Category] = {
    "llm": Category.AI,
    "llms": Category.AI,
    "agents": Category.AI,
    "machine-learning": Category.AI,
    "ml": Category.AI,
    "artificial-intelligence": Category.AI,
    "software": Category.SOFTWARE_DEVELOPMENT,
    "software-engineering": Category.SOFTWARE_DEVELOPMENT,
    "programming": Category.SOFTWARE_DEVELOPMENT,
    "security": Category.CYBERSECURITY,
    "infosec": Category.CYBERSECURITY,
    "opensource": Category.OPEN_SOURCE,
    "oss": Category.OPEN_SOURCE,
    "dev-tools": Category.DEVELOPER_TOOLS,
    "devtools": Category.DEVELOPER_TOOLS,
    "tools": Category.DEVELOPER_TOOLS,
    "database": Category.DATABASES,
    "db": Category.DATABASES,
    "infra": Category.INFRASTRUCTURE,
    "hardware": Category.INFRASTRUCTURE,
    "emerging": Category.EMERGING_TECH,
    "emerging-technologies": Category.EMERGING_TECH,
}

MAX_CATEGORIES_PER_ITEM = 3


def _lookup() -> Dict[str, str]:
    """ID, alias and label (any language, lower case) -> category ID, over every sector."""
    from .sectors import all_categories  # sectors builds on this module's tech constants

    table: Dict[str, str] = {}
    for category in all_categories():
        table.setdefault(category.id, category.id)
        for alias in category.aliases:
            table.setdefault(alias, category.id)
    for category in all_categories():
        for label in category.labels.values():
            table.setdefault(label.strip().lower(), category.id)
    return table


def parse_category(value: object) -> Optional[str]:
    """Map a category ID, alias, or label of any sector to its ID, or None if unknown."""
    if isinstance(value, Category):
        return value.value
    if not isinstance(value, str):
        return None
    table = _lookup()
    key = value.strip().lower().replace("_", "-").replace(" ", "-").replace("/", "-")
    return table.get(key) or table.get(value.strip().lower())


def normalize_categories(values: Iterable[object]) -> List[str]:
    """Return known, de-duplicated category IDs in input order (at most three)."""
    result: List[str] = []
    for value in values:
        category = parse_category(value)
        if category is not None and category not in result:
            result.append(category)
        if len(result) == MAX_CATEGORIES_PER_ITEM:
            break
    return result


def category_label(category: str, language: str) -> str:
    from .sectors import all_categories

    parsed = parse_category(category)
    for entry in all_categories():
        if entry.id == parsed:
            return entry.label(language)
    return category


def category_catalog_text(sector_id: str = "tech") -> str:
    """The sector's categories, rendered for AI prompts."""
    from .sectors import get_sector

    return "\n".join(f"- `{category.id}`: {category.scope}" for category in get_sector(sector_id).categories)


class Importance(str, Enum):
    """Editorial importance derived from the 0-10 analysis score."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


IMPORTANCE_ORDER = [Importance.LOW, Importance.MEDIUM, Importance.HIGH, Importance.CRITICAL]

IMPORTANCE_LABELS: dict[Importance, dict[str, str]] = {
    Importance.CRITICAL: {"en": "Critical", "fr": "Critique"},
    Importance.HIGH: {"en": "High", "fr": "Élevée"},
    Importance.MEDIUM: {"en": "Medium", "fr": "Moyenne"},
    Importance.LOW: {"en": "Low", "fr": "Faible"},
}


def importance_from_score(score: Optional[float]) -> Optional[Importance]:
    if score is None:
        return None
    if score >= 9:
        return Importance.CRITICAL
    if score >= 7:
        return Importance.HIGH
    if score >= 5:
        return Importance.MEDIUM
    return Importance.LOW


def importance_at_least(value: Optional[Importance], minimum: Importance) -> bool:
    if value is None:
        return False
    return IMPORTANCE_ORDER.index(value) >= IMPORTANCE_ORDER.index(minimum)
