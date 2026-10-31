"""Main orchestrator coordinating the entire workflow."""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence
import httpx
import logging
from rich.console import Console

from .console_icons import get_icons
from .models import Config, ContentItem
from .storage.manager import StorageManager
from .services.email import EmailManager
from .services.webhook import WebhookNotifier
from .scrapers.twitter import TwitterScraper
from .ai import budget
from .ai.client import create_ai_client
from .ai.analyzer import ContentAnalyzer
from .ai.summarizer import DailySummarizer
from .ai.enricher import ContentEnricher, EnrichmentBatchResult
from .ai.tokens import get_usage_snapshot
from .processing import ProfileRegistry
from .processing.tools import ToolRegistry
from .reliability.assess import ReliabilityPolicy, assess_item
from .reliability.models import SourceTier
from .newsletter.mailer import build_mailer
from .archive import ItemArchive, content_hash
from .source_health import (
    SCRAPER_SOURCE_TYPES,
    HealthStatus,
    assess_health,
    build_source_outcomes,
    configured_source_keys,
)
from .pipeline.collect import CollectionMixin, FetchReport, SourceFetchOutcome  # noqa: F401 (re-exported)
from .pipeline.deliver import DeliveryMixin
from .pipeline.select import BalancedDigestResult, FilteringPipelineResult, SelectionMixin  # noqa: F401 (re-exported)


logger = logging.getLogger(__name__)



# Identify the collector honestly; some feeds reject the default httpx agent.













class PipelineOrchestrator(CollectionMixin, SelectionMixin, DeliveryMixin):
    """Orchestrates the complete workflow for content aggregation and analysis."""

    icons = get_icons()

    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        console: Optional[Console] = None,
        profiles: Optional[ProfileRegistry] = None,
    ):
        """Initialize orchestrator.

        Args:
            config: Application configuration
            storage: Storage manager
            console: Shared Rich Console instance
        """
        self.config = config
        self.storage = storage
        self.console = console or Console(stderr=True)
        self.icons = get_icons(config.display.icon_style)
        self.profiles = profiles or ProfileRegistry.load(
            Path(config.processing.profiles_dir), config.processing.default_profile
        )
        self.profiles.validate_source_references(
            config.sources.model_dump(mode="json")
        )
        for profile_id in config.processing.profile_settings:
            self.profiles.get(profile_id)
        if config.digest.profile_order:
            configured_profiles = set(config.digest.profile_order)
            unknown_profiles = configured_profiles - self.profiles.ids
            if unknown_profiles:
                raise ValueError(
                    "digest.profile_order contains unknown profiles "
                    f"({', '.join(sorted(unknown_profiles))})"
                )
            config.digest.profile_order.extend(
                profile.id
                for profile in self.profiles.profiles
                if profile.id not in configured_profiles
            )
        self.reliability_policy = ReliabilityPolicy.with_overrides(
            config.reliability.domains, config.reliability.accounts
        )
        self.email_manager = EmailManager(config.email, console=self.console) if config.email else None
        self.mailer = (
            build_mailer(config.email, self.storage.subscribers, console=self.console)
            if config.email and config.email.enabled
            else None
        )
        self.webhook_notifier = (
            WebhookNotifier(config.webhook, console=self.console, icons=self.icons)
            if config.webhook and config.webhook.enabled
            else None
        )
        self.last_fetch_report: Optional[FetchReport] = None
        self.archive: Optional[ItemArchive] = None
        self.run_id: Optional[str] = None

    def _ai_enabled(self) -> bool:
        return bool(getattr(getattr(self.config, "ai", None), "enabled", True))

    def _open_archive(self) -> Optional[ItemArchive]:
        settings = getattr(self.config, "archive", None)
        if settings is None or not settings.enabled:
            return None
        path = Path(settings.path)
        try:
            if not path.is_absolute():
                path = Path(self.storage.data_dir) / path
            return ItemArchive(path)
        except Exception as exc:  # the digest must not depend on the archive
            logger.warning("Archive disabled for this run (%s): %s", path, exc)
            self.console.print(f"[yellow]{self.icons['warning']} Archive unavailable: {exc}[/yellow]")
            return None

    def _archive(self, method: str, *args, **kwargs) -> None:
        """Best-effort archive write; failures are logged, never raised."""
        if getattr(self, "archive", None) is None:
            return
        if method != "start_run" and getattr(self, "run_id", None) is None:
            return
        try:
            if method == "start_run":
                self.run_id = self.archive.start_run(*args, **kwargs)
            else:
                getattr(self.archive, method)(self.run_id, *args, **kwargs)
        except Exception as exc:
            logger.warning("Archive %s failed: %s", method, exc)

    async def run(self, force_hours: int = None) -> None:
        """Execute the complete workflow.

        Args:
            force_hours: Optional override for time window in hours
        """
        self.console.print(
            f"[bold cyan]{self.icons['start']} LucidNews - Starting aggregation...[/bold cyan]\n"
        )

        # Check email subscriptions if configured
        if (
            self.email_manager
            and self.config.email
            and self.config.email.enabled
            and self.config.email.imap_enabled
        ):
            self.console.print(f"{self.icons['email']} Checking for new email subscriptions...")
            self.email_manager.check_subscriptions(self.storage, self.mailer)

        try:
            budget.start_run(getattr(getattr(self.config, "ai", None), "max_tokens_per_run", None))
            if not self._ai_enabled():
                budget.mark_exhausted(budget.AILimit.DISABLED, "ai.enabled is off")
            # 1. Determine time window
            since = self._determine_time_window(force_hours)
            self.archive = self._open_archive()
            self._archive("start_run", since)
            self.console.print(
                f"{self.icons['date']} Fetching content since: "
                f"{since.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # 2. Fetch content from all sources
            all_items = await self.fetch_all_sources(since)
            self._fetched_items = all_items
            self.console.print(
                f"{self.icons['fetched']} Fetched {len(all_items)} items from all sources\n"
            )

            if self.last_fetch_report and self.last_fetch_report.all_failed:
                raise RuntimeError(self.last_fetch_report.failure_message())

            if not all_items:
                self.console.print("[yellow]No new content found. Exiting.[/yellow]")
                self._archive("record_selection_stats", url_merged=0, topic_merged=0, above_threshold=0)
                self._finish_archive("empty", all_items, [])
                await self.send_weekly_newsletters()
                return

            # 3. Merge cross-source duplicates (same URL from different sources)
            merged_items = self.merge_cross_source_duplicates(all_items)
            url_merged = len(all_items) - len(merged_items)
            if len(merged_items) < len(all_items):
                self.console.print(
                    f"{self.icons['merge']} Merged "
                    f"{len(all_items) - len(merged_items)} cross-source duplicates "
                    f"→ {len(merged_items)} unique items\n"
                )

            merged_items = self._add_pending_retries(merged_items)

            # 4. Analyze with AI
            analyzed_items = await self.analyze_items(merged_items)
            self._archive("record_items", analyzed_items)
            if budget.exhausted() is not budget.AILimit.DISABLED:
                self.console.print(
                    f"{self.icons['ai']} Analyzed {len(analyzed_items)} items with AI\n"
                )

            # Archive signals for selection: source quality and earlier reports.
            self._load_archive_signals(analyzed_items)

            # 5. Filter, deduplicate, and balance the digest
            filtering_result = await self.select_digest_items(
                analyzed_items,
            )
            important_items = filtering_result.items
            # Counters for the quality overview (url merges, topic merges, items above threshold).
            self._archive(
                "record_selection_stats",
                url_merged=url_merged,
                topic_merged=filtering_result.topic_dedup_removed,
                above_threshold=filtering_result.threshold_count,
            )
            # Only when the AI ran out of quota: items it could not analyze.
            unanalyzed = self.select_unanalyzed_items(analyzed_items)

            # Show per-sub-source selection breakdown
            selected_counts: Dict[str, int] = defaultdict(int)
            for item in important_items:
                key = f"{item.source_type.value}/{self._sub_source_label(item)}"
                selected_counts[key] += 1
            for source_key, count in sorted(selected_counts.items()):
                self.console.print(f"      {self.icons['detail']} {source_key}: {count}")
            self.console.print("")

            # 6. Search related stories + enrich with background knowledge (2nd AI pass)
            await self.enrich_items(important_items)
            self._archive("record_items", important_items, selected=True)
            self._archive("record_items", unanalyzed, selected=True)

            # 7. Generate and save daily summaries for each configured language
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for lang in self.config.ai.languages:
                summarizer = DailySummarizer(
                    profile_names=self.profiles.names,
                    profile_order=self.config.digest.profile_order,
                )
                summary = await summarizer.generate_summary(
                    important_items, today, len(all_items), language=lang, unanalyzed=unanalyzed
                )

                # Save to data/summaries/
                summary_path = self.storage.save_daily_summary(today, summary, language=lang)
                self.console.print(
                    f"{self.icons['save']} Saved {lang.upper()} summary to: {summary_path}\n"
                )

                # Send webhook notification if configured
                if self.webhook_notifier:
                    await self.webhook_notifier.send_daily_summary(
                        summary=summary,
                        important_items=important_items,
                        all_items_count=len(all_items),
                        date=today,
                        lang=lang,
                        summarizer=summarizer,
                    )

            if self.mailer is not None:
                await self.send_newsletters(
                    important_items, today, len(all_items), unanalyzed=unanalyzed
                )
                await self.send_weekly_newsletters()

            self._finish_archive("success", all_items, important_items + unanalyzed)

            self.console.print(
                f"[bold green]{self.icons['success']} "
                "LucidNews completed successfully![/bold green]"
            )
            usage = get_usage_snapshot()
            if usage.total_tokens > 0:
                max_tokens = getattr(self.config.ai, "max_tokens_per_run", None)
                self.console.print(
                    f"\n{self.icons['tokens']} Token usage this run: "
                    f"{usage.total_tokens} tokens "
                    f"(input: {usage.total_input_tokens}, output: {usage.total_output_tokens})"
                    + (f", budget {max_tokens}" if max_tokens else "")
                )
                for provider, u in sorted(usage.per_provider.items()):
                    if u.total <= 0:
                        continue
                    self.console.print(
                        f"   {self.icons['detail']} {provider}: {u.total} tokens "
                        f"(in: {u.input_tokens}, out: {u.output_tokens})"
                    )

        except Exception as e:
            self.console.print(
                f"[bold red]{self.icons['error']} Error: {e}[/bold red]"
            )
            self._finish_archive(
                "failed", getattr(self, "_fetched_items", []), [], error=str(e)
            )

            # Send webhook failure notification if configured
            if self.webhook_notifier:
                await self.webhook_notifier.send_failure(
                    date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    error_message=str(e),
                )

            raise




    def _finish_archive(
        self,
        status: str,
        fetched_items: List[ContentItem],
        selected_items: List[ContentItem],
        error: Optional[str] = None,
    ) -> None:
        """Record per-source outcomes and the run result, then flag unhealthy sources."""
        if getattr(self, "archive", None) is None or getattr(self, "run_id", None) is None:
            return
        report = getattr(self, "last_fetch_report", None)
        source_errors: Dict[str, str] = {}
        failed_types: Dict[str, str] = {}
        for outcome in report.outcomes if report else []:
            source_errors.update(outcome.source_errors)
            if outcome.status == "failure":
                source_type = SCRAPER_SOURCE_TYPES.get(outcome.source_name, outcome.source_name)
                failed_types[source_type] = outcome.error or "unknown error"
        try:
            configured = configured_source_keys(self.config)
        except Exception:
            configured = {}
        outcomes = build_source_outcomes(
            configured, fetched_items, selected_items, source_errors, failed_types
        )
        self._archive("record_source_runs", outcomes)
        limit = budget.exhausted()
        self._archive(
            "finish_run",
            status,
            fetch_report=self._fetch_report_dict(),
            error=error,
            ai_limit=limit.value if limit else None,
            tokens_used=budget.tokens_used(),
        )
        if status != "failed":
            self._warn_unhealthy_sources()

    def _warn_unhealthy_sources(self, days: int = 14) -> None:
        try:
            rows = self.archive.source_run_rows(datetime.now(timezone.utc) - timedelta(days=days))
        except Exception as exc:
            logger.warning("Source health check failed: %s", exc)
            return
        try:
            configured = set(configured_source_keys(self.config))
        except Exception:
            configured = set()
        flagged = [
            health
            for health in assess_health(rows)
            if health.status in (HealthStatus.DEAD, HealthStatus.FAILING)
            and (not configured or health.source_key in configured)
        ]
        if not flagged:
            return
        self.console.print(
            f"\n[yellow]{self.icons['warning']} {len(flagged)} source(s) need attention "
            f"(last {days} days):[/yellow]"
        )
        for health in flagged:
            self.console.print(
                f"[yellow]   {self.icons['detail']} {health.source_key}: {health.status.value}, "
                f"{'; '.join(health.reasons)}[/yellow]"
            )
        self.console.print("[dim]   Run `uv run lucidnews-sources` for the full report.[/dim]")

    def _fetch_report_dict(self) -> Optional[Dict[str, object]]:
        report = getattr(self, "last_fetch_report", None)
        return report.to_dict() if report else None

    def _reuse_archived_analyses(self, items: List[ContentItem]) -> List[ContentItem]:
        """Restore stored analyses for unchanged items; return the items still to analyze."""
        archive = getattr(self, "archive", None)
        if archive is None or not self.config.archive.reuse_analysis:
            return items
        try:
            previous = archive.get_items([item.id for item in items])
        except Exception as exc:
            logger.warning("Archive lookup failed, analyzing everything: %s", exc)
            return items

        remaining = []
        for item in items:
            stored = previous.get(item.id)
            stored_analysis = stored.processing.analysis if stored and stored.processing else None
            if (
                stored_analysis is not None
                and stored_analysis.score is not None
                and content_hash(stored) == content_hash(item)
            ):
                item.processing = stored.processing.model_copy(deep=True)
                if not getattr(self.config.archive, "reuse_enrichment", True):
                    item.processing.artifacts.clear()
                item.processing.reliability = assess_item(item, self.reliability_policy)
            else:
                remaining.append(item)
        reused = len(items) - len(remaining)
        if reused:
            self.console.print(
                f"   {self.icons['detail']} Reused {reused} analyses from the archive"
            )
        return remaining

    def _add_pending_retries(self, items: List[ContentItem]) -> List[ContentItem]:
        """Append archived items whose analysis failed in a previous run."""
        archive = getattr(self, "archive", None)
        settings = getattr(self.config, "archive", None)
        if archive is None or settings is None or not settings.retry_failed_analysis:
            return items
        try:
            pending = archive.pending_items(
                first_seen_after=datetime.now(timezone.utc)
                - timedelta(hours=settings.retry_window_hours),
                max_attempts=settings.max_analysis_attempts,
                exclude_ids=[item.id for item in items],
            )
        except Exception as exc:
            logger.warning("Could not load pending retries from the archive: %s", exc)
            return items
        if pending:
            self.console.print(
                f"{self.icons['detail']} Retrying {len(pending)} item(s) whose analysis "
                "failed in a previous run\n"
            )
        return items + pending

    async def _pause_before_retry(self, count: int, stage: str) -> bool:
        delay = getattr(self.config.ai, "failed_retry_delay_sec", None)
        if delay is None or count == 0 or budget.exhausted() is not None:
            return False
        self.console.print(
            f"[yellow]{self.icons['warning']} {count} item(s) failed {stage}; "
            f"retrying once in {delay:g}s...[/yellow]"
        )
        await asyncio.sleep(delay)
        return True

    def _determine_time_window(self, force_hours: int = None) -> datetime:
        if force_hours:
            since = datetime.now(timezone.utc) - timedelta(hours=force_hours)
        else:
            hours = self.config.collection.time_window_hours
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return since





    async def merge_topic_duplicates(
        self,
        items: List[ContentItem],
        *,
        log: bool = True,
        references: Sequence[ContentItem] = (),
    ) -> List[ContentItem]:
        """Merge items covering the same topic using AI semantic deduplication.

        This is a stable stage helper for integrations such as MCP.

        Sends all item titles, tags, and summaries to AI in a single call.
        Items must already be sorted by analysis score descending so that the first
        item in each duplicate group is always the highest-scored one.
        Content (comments) from duplicate items is merged into the primary.

        ``references`` are other reports (below the threshold, or from earlier runs
        in the archive) listed after the items: they are never kept or dropped, but
        a reference grouped with an item adds its URL to the item's corroborating
        URLs. Only official or reputable publishers are worth passing.

        Falls back to returning items unchanged if the AI call fails.
        """
        if not items or (len(items) <= 1 and not references):
            return items
        if budget.exhausted() is budget.AILimit.DISABLED:
            return items  # no AI call at all while the AI is off

        from .ai.prompting.deduplication import (
            TOPIC_DEDUP_REFERENCES,
            TOPIC_DEDUP_SYSTEM,
            TOPIC_DEDUP_USER,
        )
        from .ai.utils import parse_json_response

        # Build the item list for the prompt
        lines = []
        for i, item in enumerate([*items, *references]):
            analysis = item.processing.analysis if item.processing else None
            tags = ", ".join(analysis.tags) if analysis and analysis.tags else "—"
            summary = analysis.summary if analysis else "—"
            marker = " (reference)" if i >= len(items) else ""
            lines.append(f"[{i}]{marker} {item.title}\n    Tags: {tags}\n    Summary: {summary}")
        items_text = "\n\n".join(lines)
        if references:
            items_text += "\n\n" + TOPIC_DEDUP_REFERENCES

        try:
            ai_client = create_ai_client(self.config.ai)
            response = await ai_client.complete(
                system=TOPIC_DEDUP_SYSTEM,
                user=TOPIC_DEDUP_USER.format(items=items_text),
            )
            result = parse_json_response(response)
            if result is None:
                if log:
                    self.console.print("[yellow]  dedup: could not parse AI response, skipping[/yellow]")
                return items

            duplicate_groups = result.get("duplicates", [])
        except Exception as e:
            if log:
                self.console.print(f"[yellow]  dedup: AI call failed ({e}), skipping[/yellow]")
            return items

        if not duplicate_groups:
            return items

        # Build a set of indices to drop (all non-primary duplicates)
        drop_indices: set[int] = set()
        for group in duplicate_groups:
            if not isinstance(group, list) or len(group) < 2:
                continue
            indices = [index for index in group if isinstance(index, int) and not isinstance(index, bool)]
            members = [index for index in indices if 0 <= index < len(items)]
            if not members:
                continue  # references only: nothing to keep or drop
            primary_idx = members[0]
            primary = items[primary_idx]
            for ref_idx in indices:
                if len(items) <= ref_idx < len(items) + len(references):
                    reference = references[ref_idx - len(items)]
                    corroborating = primary.metadata.setdefault("corroborating_urls", [])
                    if str(reference.url) != str(primary.url) and str(reference.url) not in corroborating:
                        corroborating.append(str(reference.url))
                        if log:
                            self.console.print(
                                f"   [dim]corroboration: [{primary_idx}] {primary.title}[/dim]\n"
                                f"   [dim]       also reported by {reference.url}[/dim]"
                            )
            for dup_idx in members[1:]:
                if dup_idx == primary_idx:
                    continue
                dup = items[dup_idx]
                # Keep the duplicate's URLs: independent reports corroborate the primary.
                corroborating = primary.metadata.setdefault("corroborating_urls", [])
                for url in [str(dup.url), *(dup.metadata.get("corroborating_urls") or [])]:
                    if url != str(primary.url) and url not in corroborating:
                        corroborating.append(url)
                # Merge comments/content from the duplicate into the primary
                if dup.content:
                    if not primary.content or dup.content not in primary.content:
                        label = dup.source_type.value
                        primary.content = (primary.content or "") + f"\n\n--- From {label} ---\n{dup.content}"
                if log:
                    self.console.print(
                        f"   [dim]dedup: keep [{primary_idx}] {primary.title}[/dim]\n"
                        f"   [dim]       drop [{dup_idx}] {dup.title}[/dim]"
                    )
                drop_indices.add(dup_idx)

        return [item for i, item in enumerate(items) if i not in drop_indices]






    async def _expand_twitter_discussion(self, items: List[ContentItem]) -> None:
        """Second-stage: fetch reply text for important Twitter items and re-analyze.

        Only runs when sources.twitter.fetch_reply_text is True.
        Bounded by max_tweets_to_expand to control cost.
        """
        tw_cfg = self.config.sources.twitter
        if not tw_cfg or not tw_cfg.enabled or not tw_cfg.fetch_reply_text:
            return
        if budget.exhausted() is budget.AILimit.DISABLED:
            return  # the replies are only fetched to be analyzed again

        from .models import SourceType

        twitter_items = [
            item for item in items
            if item.source_type == SourceType.TWITTER
        ][:tw_cfg.max_tweets_to_expand]

        if not twitter_items:
            return

        self.console.print(
            f"{self.icons['discussion']} Fetching reply text for "
            f"{len(twitter_items)} Twitter items..."
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            if tw_cfg.mode == "playwright":
                self.console.print(
                    "   [yellow]Reply expansion not yet supported in Playwright mode.[/yellow]"
                )
                return
            scraper = TwitterScraper(tw_cfg, client)
            expanded = []
            for item in twitter_items:
                try:
                    reply_lines = await scraper.fetch_replies_for_item(item)
                    if TwitterScraper.append_discussion_content(item, reply_lines):
                        expanded.append(item)
                        self.console.print(
                            f"   {self.icons['discussion']} {len(reply_lines)} replies "
                            f"added to: {item.title[:60]}"
                        )
                except Exception as exc:
                    self.console.print(
                        f"   [yellow]{self.icons['warning']} Reply fetch failed for "
                        f"{item.id}: {exc}[/yellow]"
                    )

        if not expanded:
            return

        self.console.print(
            f"   Re-analyzing {len(expanded)} Twitter items with reply context...\n"
        )
        ai_client = create_ai_client(self.config.ai)
        analyzer = ContentAnalyzer(
            ai_client,
            self.profiles,
            console=self.console,
            reliability_policy=self.reliability_policy,
            sector=self.config.sector,
        )
        await analyzer.analyze_batch(expanded)

    async def enrich_items(self, items: List[ContentItem]) -> EnrichmentBatchResult:
        """Enrich items with background knowledge (2nd AI pass).

        For each item that passed the score threshold, call AI to generate
        background knowledge based on the item's actual content.

        Args:
            items: Important items to enrich (modified in-place)
        """
        if not items:
            return EnrichmentBatchResult()

        self.console.print(
            f"{self.icons['enrich']} Enriching with background knowledge..."
        )
        reused = self._reusable_enrichments(items)
        if reused:
            self.console.print(
                f"   {self.icons['detail']} Reused {len(reused)} enrichments from the archive"
            )
            items = [item for item in items if item.id not in reused]
            if not items:
                self.console.print("")
                return EnrichmentBatchResult(succeeded_ids=list(reused))
        if budget.exhausted() is budget.AILimit.DISABLED:
            self.console.print("")
            return EnrichmentBatchResult(succeeded_ids=list(reused))
        ai_client = create_ai_client(self.config.ai)
        enricher = ContentEnricher(
            ai_client,
            self.profiles,
            self.config.ai.languages,
            console=self.console,
            tools=ToolRegistry(self.storage.summaries_dir),
        )
        result = await enricher.enrich_batch(items)
        failed = [item for item in items if item.id in result.failures]
        if await self._pause_before_retry(len(failed), "enrichment"):
            retry = await enricher.enrich_batch(failed)
            result = EnrichmentBatchResult(
                succeeded_ids=result.succeeded_ids + retry.succeeded_ids,
                failures=retry.failures,
            )
        self.console.print(
            f"   Enriched {result.succeeded_count}/{len(items)} items"
        )
        result.succeeded_ids = list(reused) + result.succeeded_ids
        if budget.exhausted() is not None and result.failed_count:
            self.console.print(
                f"   [yellow]AI quota exhausted: {result.failed_count} item(s) keep their "
                "analysis, without enrichment[/yellow]"
            )
        elif result.failed_count:
            self.console.print(
                f"   [yellow]Skipped {result.failed_count} items after enrichment "
                f"failed: {', '.join(result.failed_ids)}[/yellow]"
            )
        self.console.print("")
        return result

    async def analyze_items(self, items: List[ContentItem]) -> List[ContentItem]:
        """Analyze content items with AI.

        Args:
            items: Items to analyze

        Returns:
            List[ContentItem]: Analyzed items
        """
        disabled = budget.exhausted() is budget.AILimit.DISABLED
        self.console.print(
            f"{self.icons['ai']} "
            + ("AI analysis is turned off: items are listed without analysis..." if disabled else "Analyzing content with AI...")
        )

        to_analyze = self._reuse_archived_analyses(items)
        if not to_analyze:
            return items

        ai_client = None
        if not disabled:
            try:
                ai_client = create_ai_client(self.config.ai)
            except ValueError as exc:
                # AI turned on but unusable (no key found): the run still lists the news.
                self.console.print(f"[yellow]{self.icons['warning']} AI analysis skipped: {exc}[/yellow]")
                budget.mark_exhausted(budget.AILimit.DISABLED, "no usable AI client")
                disabled = True
        if disabled:
            # No client is used: nothing leaves the machine.
            ContentAnalyzer(None, self.profiles, console=self.console, reliability_policy=self.reliability_policy).skip_batch(
                to_analyze, budget.AILimit.DISABLED
            )
            return items
        analyzer = ContentAnalyzer(
            ai_client,
            self.profiles,
            console=self.console,
            reliability_policy=self.reliability_policy,
            sector=self.config.sector,
        )

        await analyzer.analyze_batch(to_analyze)

        failed = [item for item in to_analyze if self._is_unscored(item)]
        if await self._pause_before_retry(len(failed), "analysis"):
            await analyzer.analyze_batch(failed)

        skipped = sum(bool(item.processing and item.processing.ai_skipped) for item in items)
        unscored = sum(self._is_unscored(item) for item in items) - skipped
        if skipped:
            limit = budget.exhausted()
            reason = (
                "token budget for this run reached"
                if limit is budget.AILimit.TOKEN_BUDGET
                else "provider quota exhausted"
            )
            self.console.print(
                f"[yellow]{self.icons['warning']} AI unavailable ({reason}): {skipped} item(s) "
                "not analyzed; they are retried in the next run[/yellow]"
            )
        if unscored:
            self.console.print(
                f"[yellow]{self.icons['warning']} {unscored} item(s) could not be scored "
                "and are left out of this digest[/yellow]"
            )
        return items

    def _reusable_enrichments(self, items: List[ContentItem]) -> List[str]:
        """Ids of items that already carry an enrichment in every configured language.

        Only an analysis reused from the archive keeps its artifacts (a new analysis
        clears them), so these are unchanged items enriched in an earlier run.
        """
        settings = getattr(self.config, "archive", None)
        if settings is None or not settings.reuse_enrichment:
            return []
        languages = set(self.config.ai.languages)
        return [
            item.id
            for item in items
            if item.processing and languages <= set(item.processing.artifacts)
        ]




    # SourceTier is declared from most to least trusted.
    _TIER_ORDER = {tier: rank for rank, tier in enumerate(SourceTier)}



