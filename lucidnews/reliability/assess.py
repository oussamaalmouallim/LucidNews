"""Combine publisher trust and claim verification into a reliability label.

Corroboration: when topic deduplication merges several reports of the same
event, their URLs are kept in ``metadata["corroborating_urls"]``. Each distinct
official or reputable site among them (other than the primary's own site) counts
as an independent corroboration.

The source tier is computed deterministically from the item's primary URL (the
page the news links to, not the channel it was discovered on: a Hacker News post
linking to a GitHub release is judged on the release). The claim status comes
from the AI analysis. The combination is rule-based and conservative: a weak
source can only reach "reliable" when the analysis found the claim confirmed,
and a rumor is always labelled as a rumor, whatever the source.
"""

import re
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from ..models import ContentItem
from .models import (
    ClaimStatus,
    ReliabilityAssessment,
    ReliabilityLabel,
    SourceTier,
)
from .accounts import account_of, normalize_account
from .registry import DEFAULT_ACCOUNT_TIERS, DEFAULT_DOMAIN_TIERS

_GITHUB_RELEASE_PATH = re.compile(r"^/[^/]+/[^/]+/releases(?:/|$)")


@dataclass(frozen=True)
class ReliabilityPolicy:
    """Domain and account registries plus project overrides."""

    domain_tiers: Mapping[str, SourceTier] = field(
        default_factory=lambda: dict(DEFAULT_DOMAIN_TIERS)
    )
    account_tiers: Mapping[str, SourceTier] = field(
        default_factory=lambda: dict(DEFAULT_ACCOUNT_TIERS)
    )

    @classmethod
    def with_overrides(
        cls,
        overrides: Optional[Mapping[str, SourceTier]] = None,
        accounts: Optional[Mapping[str, SourceTier]] = None,
    ) -> "ReliabilityPolicy":
        tiers = dict(DEFAULT_DOMAIN_TIERS)
        for domain, tier in (overrides or {}).items():
            tiers[normalize_domain(domain)] = SourceTier(tier)
        account_tiers = dict(DEFAULT_ACCOUNT_TIERS)
        for account, tier in (accounts or {}).items():
            account_tiers[normalize_account(account)] = SourceTier(tier)
        return cls(domain_tiers=tiers, account_tiers=account_tiers)

    @classmethod
    def for_config(cls, config: Any) -> "ReliabilityPolicy":
        """The registry an installation uses: the built-in list, then the authorities of its
        sector (``data/sectors/<sector>.json``), then ``reliability.domains``, which always wins."""
        from ..sector_catalog import CatalogError, load_sector_catalog

        try:
            authorities: Mapping[str, SourceTier] = load_sector_catalog(config.sector).authorities
        except CatalogError:
            authorities = {}  # a hand-edited sector without a catalog: the built-in list only
        return cls.with_overrides({**authorities, **config.reliability.domains}, config.reliability.accounts)

    def tier_for_account(self, account: Optional[str]) -> Optional[SourceTier]:
        return self.account_tiers.get(account) if account else None

    def tier_for_domain(self, host: str) -> SourceTier:
        host = normalize_domain(host)
        best: Optional[str] = None
        for domain in self.domain_tiers:
            if host == domain or host.endswith("." + domain):
                if best is None or len(domain) > len(best):
                    best = domain
        return self.domain_tiers[best] if best is not None else SourceTier.UNKNOWN


def normalize_domain(value: str) -> str:
    value = value.strip().lower()
    if "//" in value:
        value = urlsplit(value).hostname or ""
    value = value.split("/")[0].split(":")[0]
    return value.removeprefix("www.").rstrip(".")


_SECOND_LEVEL_LABELS = {"co", "com", "org", "net", "gov", "ac", "edu", "gouv"}


def site_of(domain: str) -> str:
    """Registrable site of a host: ``blog.example.co.uk`` -> ``example.co.uk``."""
    labels = normalize_domain(domain).split(".")
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL_LABELS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def tier_for_url(url: str, policy: ReliabilityPolicy) -> tuple[SourceTier, str]:
    parsed = urlsplit(url)
    domain = normalize_domain(parsed.hostname or "")
    if domain == "github.com" and _GITHUB_RELEASE_PATH.match(parsed.path):
        return SourceTier.OFFICIAL, domain
    account_tier = policy.tier_for_account(account_of(url))
    if account_tier is not None:
        # A registered account outranks the platform it posts on.
        return account_tier, domain
    return policy.tier_for_domain(domain), domain


def publisher_key(url: str) -> str:
    """Who published ``url``: the social account if any, else the registrable site.

    Two posts by different accounts on the same platform are independent publishers.
    """
    return account_of(url) or site_of(urlsplit(url).hostname or "")


def independent_corroboration(
    item: ContentItem, policy: ReliabilityPolicy
) -> List[Tuple[str, SourceTier]]:
    """Distinct official/reputable sites, other than the item's own, reporting the same event."""
    seen = {publisher_key(str(item.url))}
    result: List[Tuple[str, SourceTier]] = []
    for url in item.metadata.get("corroborating_urls") or []:
        tier, domain = tier_for_url(str(url), policy)
        publisher = publisher_key(str(url))
        if not domain or publisher in seen:
            continue
        if tier in (SourceTier.OFFICIAL, SourceTier.REPUTABLE):
            seen.add(publisher)
            result.append((account_of(str(url)) or domain, tier))
    return result


def source_tier_for(item: ContentItem, policy: ReliabilityPolicy) -> tuple[SourceTier, str, str]:
    """Return (tier, domain, reason) for an item's primary URL."""
    domain = normalize_domain(urlsplit(str(item.url)).hostname or "")

    pinned = item.metadata.get("source_trust")
    if pinned:
        try:
            return SourceTier(pinned), domain, f"source pinned as {SourceTier(pinned).value}"
        except ValueError:
            pass

    tier, domain = tier_for_url(str(item.url), policy)
    account = account_of(str(item.url))
    if account and policy.tier_for_account(account) is not None:
        return tier, domain, f"account {account} is registered as {tier.value}"
    if tier is SourceTier.OFFICIAL and domain == "github.com":
        return tier, domain, "release published in the project's own repository"
    if tier is SourceTier.UNKNOWN:
        return tier, domain, f"{domain or 'unknown host'} is not in the trust registry"
    return tier, domain, f"{domain} is registered as {tier.value}"


def combine(
    tier: SourceTier,
    claim: Optional[ClaimStatus],
    corroboration: Sequence[SourceTier] = (),
) -> ReliabilityLabel:
    if claim is ClaimStatus.RUMOR:
        # Several outlets repeating a rumor do not confirm it.
        return ReliabilityLabel.RUMOR
    if SourceTier.OFFICIAL in corroboration:
        # The party concerned published it too.
        return ReliabilityLabel.CONFIRMED
    if claim is ClaimStatus.UNVERIFIED:
        if len(corroboration) >= 2:
            return ReliabilityLabel.RELIABLE
        return ReliabilityLabel.UNVERIFIED
    base = _combine_single(tier, claim)
    if base is ReliabilityLabel.UNVERIFIED and corroboration:
        return ReliabilityLabel.RELIABLE
    return base


def _combine_single(tier: SourceTier, claim: Optional[ClaimStatus]) -> ReliabilityLabel:
    if tier is SourceTier.OFFICIAL:
        return ReliabilityLabel.CONFIRMED
    if tier is SourceTier.REPUTABLE:
        return ReliabilityLabel.RELIABLE
    # Community or unknown publisher: only an explicit confirmation lifts it.
    if claim is ClaimStatus.CONFIRMED:
        return ReliabilityLabel.RELIABLE
    return ReliabilityLabel.UNVERIFIED


def assess_item(item: ContentItem, policy: Optional[ReliabilityPolicy] = None) -> ReliabilityAssessment:
    policy = policy or ReliabilityPolicy()
    tier, domain, tier_reason = source_tier_for(item, policy)
    analysis = item.processing.analysis if item.processing else None
    claim = analysis.claim.status if analysis and analysis.claim else None

    corroboration = independent_corroboration(item, policy)
    reasons = [tier_reason]
    if corroboration:
        reasons.append(
            "corroborated by " + ", ".join(f"{domain} ({tier.value})" for domain, tier in corroboration)
        )
    if claim is None:
        reasons.append("claim status not assessed")
    else:
        evidence = analysis.claim.evidence.strip() if analysis and analysis.claim else ""
        reasons.append(f"claim {claim.value}" + (f": {evidence}" if evidence else ""))

    label = combine(tier, claim, [tier for _, tier in corroboration])
    if item.processing and item.processing.ai_skipped:
        # Nobody checked the claim: an unanalyzed headline is never shown as a fact.
        label = ReliabilityLabel.UNVERIFIED
        reasons.append("not analyzed: the AI quota was exhausted")

    return ReliabilityAssessment(
        label=label,
        source_tier=tier,
        source_domain=domain,
        claim_status=claim,
        corroborated_by=[domain for domain, _ in corroboration],
        reasons=reasons,
    )
