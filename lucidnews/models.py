"""Core data models for LucidNews."""

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Annotated, Literal, Optional, List, Dict, Any, NamedTuple, Union
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, HttpUrl, Field, ValidationError, field_validator, model_validator

from .ai.budget import AILimit
from .reliability.models import (
    ClaimAssessment,
    ReliabilityAssessment,
    ReliabilityLabel,
    SourceTier,
)
from .taxonomy import Category, normalize_categories


class SourceType(str, Enum):
    """Supported information source types."""

    GITHUB = "github"
    HACKERNEWS = "hackernews"
    RSS = "rss"
    REDDIT = "reddit"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    OSSINSIGHT = "ossinsight"
    GDELT = "gdelt"
    GOOGLE_NEWS = "google_news"


class SourceDefinition(NamedTuple):
    """How a top-level source is represented in SourcesConfig."""

    config_field: str
    config_is_list: bool = False
    item_fields: tuple[str, ...] = ()


SOURCE_REGISTRY = {
    SourceType.GITHUB.value: SourceDefinition("github", config_is_list=True),
    SourceType.HACKERNEWS.value: SourceDefinition("hackernews"),
    SourceType.RSS.value: SourceDefinition("rss", config_is_list=True),
    SourceType.REDDIT.value: SourceDefinition("reddit", item_fields=("subreddits", "users")),
    SourceType.TELEGRAM.value: SourceDefinition("telegram", item_fields=("channels",)),
    SourceType.TWITTER.value: SourceDefinition("twitter", item_fields=("users", "keywords")),
    SourceType.OSSINSIGHT.value: SourceDefinition("ossinsight"),
    SourceType.GDELT.value: SourceDefinition("gdelt"),
    SourceType.GOOGLE_NEWS.value: SourceDefinition("google_news"),
}

ProfileRoute = Optional[Union[str, List[str]]]


class ClassificationResult(BaseModel):
    """Resolved processing profile for a content item."""

    profile: str
    # "unclassified": placeholder profile for an item the AI could not reach (quota).
    method: Literal["source_override", "ai_match", "unclassified"]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason: Optional[str] = None


class ContentAnalysis(BaseModel):
    """Profile-driven first-pass analysis."""

    score: Optional[float] = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    reason: str
    summary: str
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    claim: Optional[ClaimAssessment] = None

    @field_validator("categories", mode="before")
    @classmethod
    def keep_known_categories(cls, value: object) -> List[str]:
        if not isinstance(value, list):
            return []
        return normalize_categories(value)

    @field_validator("claim", mode="before")
    @classmethod
    def drop_invalid_claim(cls, value: object) -> object:
        """An unusable claim block degrades to "not assessed" instead of failing analysis."""
        if value is None or isinstance(value, ClaimAssessment):
            return value
        try:
            return ClaimAssessment.model_validate(value)
        except ValidationError:
            return None


class ArtifactSource(BaseModel):
    """External source used while producing an artifact."""

    id: str
    title: str
    url: str


class ContentBlock(BaseModel):
    """A renderable section produced by an enrichment profile."""

    id: str
    type: Literal["section"] = "section"
    title: str
    content: str
    source_refs: List[str] = Field(default_factory=list)
    primary: bool = False


class ContentArtifact(BaseModel):
    """Localized, profile-defined enriched content."""

    language: str
    title: str
    blocks: List[ContentBlock] = Field(default_factory=list)
    sources: List[ArtifactSource] = Field(default_factory=list)


class ProcessingResult(BaseModel):
    """All AI processing state for a content item."""

    classification: ClassificationResult
    analysis: Optional[ContentAnalysis] = None
    reliability: Optional[ReliabilityAssessment] = None
    artifacts: Dict[str, ContentArtifact] = Field(default_factory=dict)
    # Set when the item was not analyzed because the run ran out of AI quota.
    ai_skipped: Optional[AILimit] = None


class ContentItem(BaseModel):
    """Unified content item model from any source."""

    model_config = ConfigDict(extra="forbid")

    id: str  # Format: {source}:{subtype}:{native_id}
    source_type: SourceType
    title: str
    url: HttpUrl
    content: Optional[str] = None
    author: Optional[str] = None
    published_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    profile: ProfileRoute = None
    processing: Optional[ProcessingResult] = None


class AIProvider(str, Enum):
    """Supported AI providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    ALI = "ali"
    GEMINI = "gemini"
    DOUBAO = "doubao"
    MINIMAX = "minimax"
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"


# Provider-specific defaults used by setup and provider-chain expansion.
AI_PROVIDER_DEFAULTS = {
    AIProvider.ANTHROPIC: {
        "model": "claude-3-5-sonnet-20241022",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": None,
    },
    AIProvider.OPENAI: {
        "model": "gpt-4",
        "api_key_env": "OPENAI_API_KEY",
        "base_url": None,
    },
    AIProvider.AZURE: {
        "model": "gpt-4",
        "api_key_env": "AZURE_OPENAI_API_KEY",
        "base_url": None,
        "azure_endpoint_env": "AZURE_OPENAI_ENDPOINT",
        "api_version": "2024-10-21",
    },
    AIProvider.ALI: {
        "model": "qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    AIProvider.GEMINI: {
        "model": "gemini-1.5-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "base_url": None,
    },
    AIProvider.DOUBAO: {
        "model": "doubao-pro-32k",
        "api_key_env": "DOUBAO_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    AIProvider.MINIMAX: {
        "model": "MiniMax-M3",
        "api_key_env": "MINIMAX_API_KEY",
        "base_url": "https://api.minimax.io/v1",
    },
    AIProvider.DEEPSEEK: {
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    },
    AIProvider.OLLAMA: {
        "model": "llama3.1",
        "api_key_env": "",
        "base_url": "http://localhost:11434/v1",
    },
}


class AIConfig(BaseModel):
    """AI client configuration."""

    # Opt-in. Off: nothing is sent to an AI provider, no key is needed, and the run lists the
    # collected items without analysis (same as when the quota runs out).
    enabled: bool = False
    provider: AIProvider
    provider_chain: Optional[str] = None
    model: str
    base_url: Optional[str] = None
    api_key_env: str
    temperature: float = 0.3
    max_tokens: int = 4096
    throttle_sec: float = 0.0
    # Provider quota, e.g. 5 for Gemini free tier on gemini-2.5-flash. None = unlimited.
    max_requests_per_minute: Optional[int] = Field(default=None, gt=0)
    # Token budget for one run (all AI stages). Once reached, the AI is no longer
    # called and the rest of the run goes on without it. None = no budget.
    max_tokens_per_run: Optional[int] = Field(default=None, gt=0)
    # Items whose analysis or enrichment failed are retried once at the end of the
    # stage after this pause (lets per-minute quotas reset). None disables it.
    failed_retry_delay_sec: Optional[float] = Field(default=30.0, ge=0)
    analysis_concurrency: int = 1
    enrichment_concurrency: int = 1
    languages: List[str] = Field(default_factory=lambda: ["en"])
    # Azure OpenAI specific; required when provider == AZURE
    azure_endpoint_env: Optional[str] = None
    api_version: Optional[str] = None

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, languages: List[str]) -> List[str]:
        """Allow conventional language tags while excluding path syntax."""
        language_tag = re.compile(r"^[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*$")
        invalid = [language for language in languages if not language_tag.fullmatch(language)]
        if invalid:
            raise ValueError(f"invalid language code: {invalid[0]!r}")
        return languages


class GitHubSourceConfig(BaseModel):
    """GitHub source configuration."""

    type: str  # "user_events", "repo_releases", etc.
    username: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None
    enabled: bool = True
    category: Optional[str] = None
    profile: ProfileRoute = None

    @model_validator(mode="after")
    def normalize_repo(self) -> "GitHubSourceConfig":
        """Accept a pasted repository URL or "owner/repo" in ``repo``."""
        if not self.repo or "/" not in self.repo:
            return self
        path = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", self.repo.strip())
        parts = [part for part in path.removesuffix(".git").split("/") if part]
        if len(parts) != 2:
            raise ValueError(
                f"github repo must be a repository name or owner/repo, got {self.repo!r}"
            )
        owner, repo = parts
        if self.owner and self.owner.lower() != owner.lower():
            raise ValueError(
                f"github repo {self.repo!r} does not belong to owner {self.owner!r}"
            )
        self.owner, self.repo = owner, repo
        return self


class HackerNewsConfig(BaseModel):
    """Hacker News configuration."""

    enabled: bool = True
    fetch_top_stories: int = 30
    min_score: int = 100
    category: Optional[str] = None
    profile: ProfileRoute = None


class ExtractorType(str, Enum):
    TRAFILATURA = "trafilatura"


class TrafilaturaExtractorConfig(BaseModel):
    type: Literal[ExtractorType.TRAFILATURA] = ExtractorType.TRAFILATURA
    favor_precision: bool = False
    favor_recall: bool = False


ExtractorConfig = Annotated[
    Union[TrafilaturaExtractorConfig],
    Field(discriminator="type"),
]


class RSSSourceConfig(BaseModel):
    """RSS feed source configuration."""

    name: str
    url: HttpUrl
    enabled: bool = True
    category: Optional[str] = None
    content_extractor: Optional[str] = None
    profile: ProfileRoute = None
    trust: Optional[SourceTier] = None  # pin the publisher tier for this feed's items


class RedditSubredditConfig(BaseModel):
    """Configuration for monitoring a specific subreddit."""

    subreddit: str
    enabled: bool = True
    sort: str = "hot"  # hot, new, top, rising
    time_filter: str = (
        "day"  # hour, day, week, month, year, all (only for top/controversial)
    )
    fetch_limit: int = 25
    min_score: int = 10
    category: Optional[str] = None
    profile: ProfileRoute = None


class RedditUserConfig(BaseModel):
    """Configuration for monitoring a specific Reddit user."""

    username: str  # without u/ prefix
    enabled: bool = True
    sort: str = "new"
    fetch_limit: int = 10
    category: Optional[str] = None
    profile: ProfileRoute = None


class RedditConfig(BaseModel):
    """Reddit source configuration."""

    enabled: bool = True
    subreddits: List[RedditSubredditConfig] = Field(default_factory=list)
    users: List[RedditUserConfig] = Field(default_factory=list)
    fetch_comments: int = 5  # top comments per post, 0 to disable


class TelegramChannelConfig(BaseModel):
    """Configuration for monitoring a specific Telegram channel."""

    channel: str  # channel username, e.g. "zaihuapd"
    enabled: bool = True
    fetch_limit: int = 20
    category: Optional[str] = None
    profile: ProfileRoute = None


class TelegramConfig(BaseModel):
    """Telegram source configuration."""

    enabled: bool = True
    channels: List[TelegramChannelConfig] = Field(default_factory=list)


class TwitterConfig(BaseModel):
    """Twitter source configuration.

    Two modes are supported:
    - "apify": Use Apify scweet actor (requires APIFY_TOKEN, more reliable)
    - "playwright": Use Playwright + browser cookies (free, no token needed)

    `keywords` uses Apify search mode. Playwright logs a warning and skips them.
    """

    enabled: bool = True
    mode: str = "apify"  # "apify" or "playwright"
    users: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    fetch_limit: int = 10
    category: Optional[str] = None
    profile: ProfileRoute = None
    fetch_reply_text: bool = False
    max_replies_per_tweet: int = 3
    max_tweets_to_expand: int = 10
    reply_min_likes: int = 0
    # Apify settings (used when mode == "apify")
    apify_token_env: str = "APIFY_TOKEN"
    actor_id: str = "altimis~scweet"
    # Playwright settings (used when mode == "playwright")
    cookie_dir: str = "data"
    cookie_file_pattern: str = "x_cookies_*.json"


class OSSInsightConfig(BaseModel):
    """OSS Insight trending repos source configuration.

    Pulls top star-gain repositories from the OSS Insight public API and
    emits them as ContentItems. Optional `keywords` filter limits results
    to repos whose description, repo name, or collection names contain at
    least one of the listed substrings (case-insensitive). Leave
    `keywords` empty to ingest everything trending in the configured
    languages.
    """

    enabled: bool = False
    period: str = "past_24_hours"  # past_24_hours, past_28_days
    languages: List[str] = Field(
        default_factory=lambda: ["All", "Python", "TypeScript"]
    )
    keywords: List[str] = Field(default_factory=list)
    min_stars: int = 5
    max_items: int = 30
    category: Optional[str] = None
    profile: ProfileRoute = None


class GDELTConfig(BaseModel):
    """GDELT 2.0 DOC API source configuration.

    Queries the key-less GDELT DOC API
    (https://api.gdeltproject.org/api/v2/doc/doc) for recent news articles
    matching a search query and emits them as ContentItems. No API key is
    required. The DOC API caps results at 250 records per request, so keep
    `max_records` modest.
    """

    enabled: bool = False
    query: str = "artificial intelligence"
    mode: str = "ArtList"
    max_records: int = 75  # GDELT DOC API caps at 250; keep modest
    timespan: Optional[str] = None  # e.g. "24h"; overrides since-derived window
    language: Optional[str] = None  # sourcelang filter, e.g. "english"; None = no filter
    country: Optional[str] = None  # sourcecountry filter; None = no filter
    category: Optional[str] = None  # LucidNews category label for downstream grouping
    profile: ProfileRoute = None


class GoogleNewsConfig(BaseModel):
    """Google News RSS search source configuration.

    Builds Google News RSS search URLs
    (https://news.google.com/rss/search) for a query and parses the
    resulting feed via feedparser. No API key is required.
    """

    enabled: bool = False
    query: str = "artificial intelligence"
    language: str = "en"  # hl
    country: str = "US"  # gl
    ceid: Optional[str] = None  # when None scraper derives it as "{country}:{language}"
    max_results: int = 100  # cap ~100
    category: Optional[str] = None
    profile: ProfileRoute = None


class SourcesConfig(BaseModel):
    """All sources configuration."""

    github: List[GitHubSourceConfig] = Field(default_factory=list)
    hackernews: HackerNewsConfig = Field(default_factory=HackerNewsConfig)
    rss: List[RSSSourceConfig] = Field(default_factory=list)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    twitter: Optional[TwitterConfig] = None
    ossinsight: OSSInsightConfig = Field(default_factory=OSSInsightConfig)
    gdelt: Optional[GDELTConfig] = None
    google_news: Optional[GoogleNewsConfig] = None


class WebhookConfig(BaseModel):
    """Webhook notification configuration."""

    url_env: Optional[str] = (
        None  # Environment variable name containing the webhook URL
    )
    request_body: Optional[Union[str, dict, list]] = (
        None  # POST body: real JSON object or string with #{key} placeholders; if empty, will use GET
    )
    headers: Optional[str] = None  # Custom headers, "Key: Value" per line
    delivery: str = "summary"  # summary, or summary_and_items
    overview_position: str = "first"  # For summary_and_items: first, or last
    platform: str = "generic"  # generic, feishu, lark, dingtalk, slack, discord
    layout: str = "markdown"  # markdown, or collapsible
    fallback_layout: str = (
        "markdown"  # Layout to use when the requested layout is unsupported
    )
    languages: Optional[List[str]] = (
        None  # Optional language filter for webhook delivery; defaults to all AI languages
    )
    enabled: bool = False

    @field_validator("delivery")
    @classmethod
    def validate_delivery(cls, v: str) -> str:
        allowed = {"summary", "summary_and_items"}
        if v not in allowed:
            raise ValueError(f"webhook.delivery must be one of {allowed}, got '{v}'")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        allowed = {"generic", "feishu", "lark", "dingtalk", "slack", "discord"}
        if v not in allowed:
            raise ValueError(f"webhook.platform must be one of {allowed}, got '{v}'")
        return v

    @field_validator("layout")
    @classmethod
    def validate_layout(cls, v: str) -> str:
        allowed = {"markdown", "collapsible"}
        if v not in allowed:
            raise ValueError(f"webhook.layout must be one of {allowed}, got '{v}'")
        return v

    @field_validator("fallback_layout")
    @classmethod
    def validate_fallback_layout(cls, v: str) -> str:
        allowed = {"markdown", "collapsible"}
        if v not in allowed:
            raise ValueError(
                f"webhook.fallback_layout must be one of {allowed}, got '{v}'"
            )
        return v

    @field_validator("overview_position")
    @classmethod
    def validate_overview_position(cls, v: str) -> str:
        allowed = {"first", "last"}
        if v not in allowed:
            raise ValueError(
                f"webhook.overview_position must be one of {allowed}, got '{v}'"
            )
        return v


class EmailConfig(BaseModel):
    """Email configuration for updates/subscriptions."""

    imap_server: str
    imap_port: int = 993
    imap_enabled: bool = True
    smtp_server: str
    smtp_port: int = 465
    smtp_username: Optional[str] = None
    email_address: str
    password_env: str = "EMAIL_PASSWORD"
    sender_name: str = "LucidNews Daily"
    subscribe_keyword: str = "SUBSCRIBE"
    unsubscribe_keyword: str = "UNSUBSCRIBE"
    enabled: bool = False
    # Weekly subscribers get the best items of the last 7 days on this weekday of the
    # first run of that day (0 = Monday ... 6 = Sunday), at most once per ISO week.
    weekly_day: int = Field(default=0, ge=0, le=6)
    weekly_max_items: int = Field(default=15, gt=0, le=100)
    # How e-mails leave: "smtp" (the server above) or "resend" (Resend's HTTPS API).
    provider: Literal["smtp", "resend"] = "smtp"
    resend_api_key_env: str = "RESEND_API_KEY"
    # Secret that signs confirmation and unsubscription links (at least 16 characters).
    signing_key_env: str = "NEWSLETTER_SIGNING_KEY"
    # Where readers open those links: the address of the public service (`lucidnews-public`).
    public_base_url: Optional[str] = None

    @field_validator("public_base_url")
    @classmethod
    def validate_public_base_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.query or parsed.fragment:
            raise ValueError("public_base_url must be an http(s) address without query or fragment")
        if parsed.scheme == "http" and not local:
            raise ValueError("public_base_url must use https (http is only accepted for localhost)")
        return value


class CategoryGroupConfig(BaseModel):
    """A quota group containing one or more source categories."""

    name: Optional[str] = None
    limit: int = Field(gt=0)
    categories: List[str] = Field(min_length=1)


class ProfileSettingsConfig(BaseModel):
    """User preferences applied to a processing profile at runtime."""

    model_config = ConfigDict(extra="forbid")

    threshold: Optional[float] = Field(default=None, ge=0, le=10)
    topic_dedup: bool = True


class ProcessingConfig(BaseModel):
    """Profile discovery and fallback settings."""

    model_config = ConfigDict(extra="forbid")

    profiles_dir: str = "profiles"
    default_profile: str = "tech-news"
    profile_settings: Dict[str, ProfileSettingsConfig] = Field(default_factory=dict)


class DisplayConfig(BaseModel):
    """Controls terminal output presentation."""

    model_config = ConfigDict(extra="forbid")

    icon_style: Literal["emoji", "nerd", "ascii"] = "emoji"


class CollectionConfig(BaseModel):
    """Controls which source items are fetched."""

    model_config = ConfigDict(extra="forbid")

    time_window_hours: int = 24


class DigestConfig(BaseModel):
    """Controls grouping and limits in the final digest."""

    model_config = ConfigDict(extra="forbid")

    max_items: Optional[int] = Field(default=None, gt=0)
    category_groups: Dict[str, CategoryGroupConfig] = Field(default_factory=dict)
    default_group: str = "other"
    default_group_limit: Optional[int] = Field(default=None, gt=0)
    profile_order: List[str] = Field(default_factory=list)
    # Only when the AI quota runs out: how many items the AI could not analyze are
    # still published, in a separate "not analyzed" section. 0 publishes none.
    unanalyzed_max_items: int = Field(default=15, ge=0)
    # Window of archived items used for the source quality score (tie-breaker
    # between items of equal AI score). 0 disables it.
    source_quality_days: int = Field(default=30, ge=0)
    # Domains (taxonomy categories) the reader follows. Coverage gaps are only
    # reported for them; with only_watched_categories, the digest keeps only items
    # the AI placed in at least one of them.
    watched_categories: List[str] = Field(default_factory=lambda: [category.value for category in Category])
    only_watched_categories: bool = False
    # A watched domain is a coverage gap below either threshold (over the period shown).
    coverage_min_sources: int = Field(default=2, ge=0, le=50)
    coverage_min_items: int = Field(default=3, ge=0, le=1000)

    @field_validator("watched_categories")
    @classmethod
    def validate_watched_categories(cls, value: List[str]) -> List[str]:
        known = {category.value for category in Category}
        unknown = [entry for entry in value if entry not in known]
        if unknown:
            raise ValueError(f"unknown categories: {', '.join(map(str, unknown))}")
        # Taxonomy order, no duplicates: the same choice is always written the same way.
        return [category.value for category in Category if category.value in value]

    @model_validator(mode="after")
    def require_a_watched_category(self) -> "DigestConfig":
        if self.only_watched_categories and not self.watched_categories:
            raise ValueError("choose at least one watched category to publish only watched categories")
        return self

    @field_validator("profile_order")
    @classmethod
    def validate_profile_order(cls, value: List[str]) -> List[str]:
        if any(not profile_id.strip() for profile_id in value):
            raise ValueError("digest.profile_order entries must be non-empty strings")
        if len(value) != len(set(value)):
            raise ValueError("digest.profile_order entries must be unique")
        return value


class ArchiveConfig(BaseModel):
    """SQLite archive of runs and processed items."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    path: str = "archive.sqlite3"  # relative paths resolve under the data directory
    # Reuse a stored analysis when the same item comes back unchanged (saves AI quota).
    reuse_analysis: bool = True
    # Also reuse its enrichment (translated summary, context) when every configured
    # language is already there.
    reuse_enrichment: bool = True
    # Items whose analysis failed are retried in later runs, even outside the window.
    retry_failed_analysis: bool = True
    retry_window_hours: int = Field(default=48, gt=0)
    max_analysis_attempts: int = Field(default=3, ge=1)


class ReliabilityConfig(BaseModel):
    """Source trust registry overrides and digest reliability policy."""

    model_config = ConfigDict(extra="forbid")

    domains: Dict[str, SourceTier] = Field(default_factory=dict)
    # Social accounts as publishers: {"x:openai": "official", "mastodon:user@host": "reputable"}
    accounts: Dict[str, SourceTier] = Field(default_factory=dict)
    exclude_labels: List[ReliabilityLabel] = Field(default_factory=list)
    # Wider corroboration: official/reputable reports below the threshold or from
    # earlier runs (archive, this many hours back) can corroborate a digest item.
    corroboration_lookback_hours: int = Field(default=72, ge=0)
    # Max reference reports sent with each topic dedup call. 0 disables it.
    corroboration_max_references: int = Field(default=30, ge=0)

    @field_validator("accounts")
    @classmethod
    def normalize_accounts(cls, value: Dict[str, SourceTier]) -> Dict[str, SourceTier]:
        from .reliability.accounts import normalize_account

        return {normalize_account(account): tier for account, tier in value.items()}


class AuthConfig(BaseModel):
    """Accounts for the web app (see ``lucidnews/auth``). Off by default: the app stays open."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allow_signup: bool = True
    session_days: int = Field(default=30, ge=1, le=365)
    # Address the browser uses to reach the app, e.g. http://localhost:5173 or https://news.example.com.
    # Needed behind a reverse proxy and for Google (redirect URI); a Host header is only trusted for localhost.
    public_url: Optional[str] = None
    # NAMES of the environment variables holding the Google OAuth client; never the values.
    google_client_id_env: str = "GOOGLE_CLIENT_ID"
    google_client_secret_env: str = "GOOGLE_CLIENT_SECRET"

    @field_validator("public_url")
    @classmethod
    def validate_public_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        parts = urlsplit(value.strip())
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("public_url must be an origin such as https://news.example.com")
        return f"{parts.scheme}://{parts.netloc}"


class ServerConfig(BaseModel):
    """The web API process (``lucidnews-api``): who the client is, and how often it may call."""

    model_config = ConfigDict(extra="forbid")

    # Reverse proxies (IP addresses) allowed to name the client in X-Forwarded-For. Empty: the
    # connection's peer is the client. Behind Caddy on the same machine: ["127.0.0.1", "::1"].
    trusted_proxies: List[str] = Field(default_factory=list)
    # Requests per minute and client on /api; the costly routes (search, period) get a fifth of it.
    requests_per_minute: int = Field(default=240, ge=10, le=10_000)

    @field_validator("trusted_proxies")
    @classmethod
    def ip_addresses(cls, value: List[str]) -> List[str]:
        import ipaddress

        result = []
        for entry in value:
            try:
                result.append(str(ipaddress.ip_address(entry.strip())))
            except ValueError as exc:
                raise ValueError(f"not an IP address: {entry}") from exc
        return result


class Config(BaseModel):
    """Main configuration model."""

    model_config = ConfigDict(extra="forbid")

    ai: AIConfig
    sources: SourcesConfig
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
    digest: DigestConfig = Field(default_factory=DigestConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    reliability: ReliabilityConfig = Field(default_factory=ReliabilityConfig)
    archive: ArchiveConfig = Field(default_factory=ArchiveConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    extractors: Dict[str, ExtractorConfig] = Field(default_factory=dict)
    email: Optional[EmailConfig] = None
    webhook: Optional[WebhookConfig] = None
    auth: AuthConfig = Field(default_factory=AuthConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
