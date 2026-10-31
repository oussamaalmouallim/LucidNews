"""Prompt construction for profile-driven content analysis."""

from ...models import ContentItem
from ...processing.profiles import LoadedProfile
from ...taxonomy import category_catalog_text
from .common import EVIDENCE_RULES, UNTRUSTED_INPUT_RULE

ANALYSIS_RULES = f"""You are a content curator evaluating an item under the supplied processing profile.

- {UNTRUSTED_INPUT_RULE}
- Base the analysis only on the supplied item and its metadata.
{EVIDENCE_RULES}
- Apply the profile's evaluation policy consistently."""

VERIFICATION_RULES = """Judge how well the item's main claim is supported, using only the supplied evidence:
- `confirmed`: announced, documented, or shipped by the party it concerns (official post, release notes, docs, filing), or directly demonstrated in the item.
- `reported`: stated by a credible outlet or expert, but not by the party it concerns.
- `unverified`: a single weak or unclear source, or the evidence does not support the headline.
- `rumor`: leaks, anonymous sources, speculation, predictions, or "reportedly/allegedly" claims.
Popularity, votes, and comments are not evidence. When unsure between two levels, choose the weaker one."""


def analysis_system_prompt(profile: LoadedProfile, sector: str = "tech") -> str:
    return f"""{ANALYSIS_RULES}

# Profile policy

{profile.analysis_prompt}

# Categories

Assign one to three categories from this catalog, most relevant first:
{category_catalog_text(sector)}

# Claim verification

{VERIFICATION_RULES}

# Output contract

Return valid JSON only:
{{
  "score": <number from 0 to 10>,
  "reason": "<concise explanation>",
  "summary": "<one-sentence summary>",
  "tags": ["<tag>", "..."],
  "categories": ["<category ID>"],
  "claim": {{"status": "confirmed|reported|unverified|rumor", "evidence": "<what supports or undermines the claim>"}}
}}"""


def analysis_user_prompt(
    item: ContentItem,
    content_section: str,
    discussion_section: str,
) -> str:
    return f"""Analyze the following content.

Title: {item.title}
Source: {item.source_type.value}
Author: {item.author or "Unknown"}
URL: {item.url}
{content_section}
{discussion_section}"""
