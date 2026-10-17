import { z } from 'zod'

// Mirrors lucidnews/web_api.py. Parsing at the boundary keeps the UI honest about the data.

export const reliabilityLabels = ['confirmed', 'reliable', 'unverified', 'rumor'] as const
export const sourceTiers = ['official', 'reputable', 'community', 'unknown'] as const

const reliabilitySchema = z.object({
  label: z.enum(reliabilityLabels),
  source_tier: z.enum(sourceTiers),
  source_domain: z.string(),
  claim_status: z.string().nullable(),
  corroborated_by: z.array(z.string()),
  reasons: z.array(z.string()),
})

const itemSchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  score: z.number().nullable(),
  importance: z.enum(['critical', 'high', 'medium', 'low']).nullable(),
  categories: z.array(z.string()),
  tags: z.array(z.string()),
  summary: z.string(),
  sections: z.array(z.object({ id: z.string(), title: z.string(), content: z.string() })),
  reliability: reliabilitySchema.nullable(),
  source_type: z.string(),
  author: z.string().nullable(),
  published_at: z.string(),
  discussion_url: z.string().nullable().optional(),
  translated: z.boolean(),
  /** Not analyzed: the AI quota ran out. Original headline, no AI content. */
  ai_skipped: z.boolean().default(false),
})

/** The 12 domains (taxonomy categories), in the order the digest uses. */
export const domainCategories = [
  'ai',
  'software-development',
  'cloud',
  'devops',
  'data',
  'cybersecurity',
  'web',
  'open-source',
  'developer-tools',
  'databases',
  'infrastructure',
  'emerging-tech',
] as const

export const aiLimits = ['provider_quota', 'token_budget', 'disabled'] as const

const runSchema = z.object({
  id: z.string(),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  fetched_count: z.number(),
  selected_count: z.number(),
  /** Why the AI did not analyze (some of) the run: AI turned off, daily quota, or the run's token budget. */
  ai_limit: z.enum(aiLimits).nullable().default(null),
  tokens_used: z.number().default(0),
  ai_skipped_count: z.number().default(0),
})

export const editionListSchema = z.object({ editions: z.array(runSchema) })

export const healthStatuses = ['dead', 'failing', 'silent', 'noisy', 'healthy'] as const

const sourceHealthSchema = z.object({
  source: z.string(),
  type: z.string(),
  status: z.enum(healthStatuses),
  runs: z.number(),
  failures: z.number(),
  consecutive_failures: z.number(),
  empty_runs: z.number(),
  items: z.number(),
  selected: z.number(),
  selection_rate: z.number(),
  last_success_at: z.string().nullable(),
  last_error: z.string().nullable(),
  /** 0..1, from the archive; only breaks ties between items of equal AI score. */
  quality: z.object({ score: z.number(), items: z.number(), mean_score: z.number(), trusted_share: z.number() }).nullable().default(null),
})

export const sourceReportSchema = z.object({
  days: z.number(),
  quality_days: z.number().default(30),
  sources: z.array(sourceHealthSchema),
  configured_without_history: z.array(z.string()),
  runs: z.array(runSchema),
})

export const editionSchema = runSchema.extend({
  language: z.string(),
  available_languages: z.array(z.string()),
  sections: z.array(z.object({ profile: z.string(), name: z.string(), items: z.array(itemSchema) })),
  /** Items published without analysis because the AI quota ran out. */
  unanalyzed: z.array(itemSchema).default([]),
})

export const claimStatuses = ['confirmed', 'reported', 'unverified', 'rumor'] as const

export const itemDetailSchema = itemSchema.extend({
  language: z.string(),
  available_languages: z.array(z.string()),
  profile: z.string(),
  profile_name: z.string(),
  claim: z.object({ status: z.enum(claimStatuses), evidence: z.string() }).nullable(),
  editions: z.array(runSchema),
})

export type ItemDetail = z.infer<typeof itemDetailSchema>
export type ClaimStatus = (typeof claimStatuses)[number]
export type Run = z.infer<typeof runSchema>
export type AiLimit = (typeof aiLimits)[number]
export type Edition = z.infer<typeof editionSchema>
export type SourceReport = z.infer<typeof sourceReportSchema>
export type SourceHealth = z.infer<typeof sourceHealthSchema>
export type HealthStatus = (typeof healthStatuses)[number]
export type EditionItem = z.infer<typeof itemSchema>
export type Reliability = z.infer<typeof reliabilitySchema>
export type ReliabilityLabel = (typeof reliabilityLabels)[number]
export type SourceTier = (typeof sourceTiers)[number]

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Field-level validation messages from the API (422/409). */
    readonly fields: Record<string, string> = {},
    /** Stable machine-readable reason from the API (auth routes). */
    readonly code?: string,
  ) {
    super(message)
  }
}

export const UNAUTHORIZED_EVENT = 'lucidnews:unauthorized'

async function request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    // A session that ended: let the shell send the reader back to the sign-in page.
    if (response.status === 401 && !path.startsWith('/api/auth')) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    throw new ApiError(body?.error ?? `API responded ${response.status}`, response.status, body?.fields ?? {}, body?.code)
  }
  return schema.parse(await response.json())
}

function getJson<T>(path: string, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  return request(path, schema, { signal })
}

export function fetchEdition(id: string, language: string, signal?: AbortSignal): Promise<Edition> {
  return getJson(`/api/editions/${encodeURIComponent(id)}?lang=${encodeURIComponent(language)}`, editionSchema, signal)
}

export async function fetchEditions(signal?: AbortSignal): Promise<Run[]> {
  return (await getJson('/api/editions', editionListSchema, signal)).editions
}

/** Every published edition (up to the API's cap), for the date filter of the Edition page. */
export async function fetchAllEditions(signal?: AbortSignal): Promise<Run[]> {
  return (await getJson('/api/editions?limit=2000', editionListSchema, signal)).editions
}

export const periodSchema = editionSchema.extend({
  edition_count: z.number(),
  /** Analyzed items found in the period (all of them are listed). */
  analyzed_total: z.number(),
})
export type Period = z.infer<typeof periodSchema>

export function fetchPeriod(since: Date, until: Date, language: string, signal?: AbortSignal): Promise<Period> {
  const query = new URLSearchParams({ since: since.toISOString(), until: until.toISOString(), lang: language })
  return getJson(`/api/editions/period?${query}`, periodSchema, signal)
}

export function fetchSourceReport(days: number, signal?: AbortSignal): Promise<SourceReport> {
  return getJson(`/api/sources?days=${days}`, sourceReportSchema, signal)
}

export function fetchItem(id: string, language: string, signal?: AbortSignal): Promise<ItemDetail> {
  return getJson(`/api/items/${encodeURIComponent(id)}?lang=${encodeURIComponent(language)}`, itemDetailSchema, signal)
}

// Subscriber preferences (local-only routes, see lucidnews/subscribers_api.py) -------------

export const frequencies = ['daily', 'weekly'] as const
export const subscriptionStatuses = ['pending', 'confirmed', 'unsubscribed'] as const
export const detailLevels = ['brief', 'complete'] as const
export const importanceLevels = ['low', 'medium', 'high', 'critical'] as const

export const preferencesSchema = z.object({
  language: z.string(),
  categories: z.array(z.string()),
  sources: z.array(z.string()),
  frequency: z.enum(frequencies),
  min_importance: z.enum(importanceLevels).nullable(),
  include_unconfirmed: z.boolean(),
  max_items: z.number().int().nullable(),
  detail_level: z.enum(detailLevels),
})

const subscriberSchema = z.object({
  id: z.string(),
  email: z.string(),
  plan: z.enum(['free', 'premium']),
  preferences: preferencesSchema,
  created_at: z.string(),
  /** Pending readers receive nothing until they open the confirmation link. */
  status: z.enum(subscriptionStatuses),
  confirmed_at: z.string().nullable().default(null),
  unsubscribed_at: z.string().nullable().default(null),
})

const optionsSchema = z.object({
  languages: z.array(z.object({ code: z.string(), name: z.string() })),
  categories: z.array(z.string()),
  frequencies: z.array(z.enum(frequencies)),
  detail_levels: z.array(z.enum(detailLevels)),
  weekly_day: z.number().int().min(0).max(6),
  importance_levels: z.array(z.enum(importanceLevels)),
  sources: z.array(z.object({ value: z.string(), type: z.string(), kind: z.enum(['type', 'source']) })),
  plans: z.array(
    z.object({
      id: z.enum(['free', 'premium']),
      max_categories: z.number().nullable(),
      max_sources: z.number().nullable(),
      max_items: z.number().nullable(),
    }),
  ),
})

const newsletterPreviewSchema = z.object({
  frequency: z.enum(frequencies),
  detail_level: z.enum(detailLevels),
  language: z.string(),
  weekly_day: z.number().int(),
  reason: z.string().nullable(),
  subject: z.string().nullable(),
  html: z.string().nullable(),
  text: z.string().nullable(),
  item_count: z.number().int(),
  unanalyzed_count: z.number().int(),
  empty: z.boolean(),
  would_send: z.boolean(),
  edition: z.string().optional(),
  since: z.string().optional(),
  until: z.string().optional(),
  language_fallback: z.object({ wanted: z.string(), used: z.string() }).optional(),
})

export type NewsletterPreview = z.infer<typeof newsletterPreviewSchema>
export type Preferences = z.infer<typeof preferencesSchema>
export type Subscriber = z.infer<typeof subscriberSchema>
export type PreferenceOptions = z.infer<typeof optionsSchema>

export function fetchPreferenceOptions(signal?: AbortSignal): Promise<PreferenceOptions> {
  return getJson('/api/preferences/options', optionsSchema, signal)
}

export async function fetchSubscribers(signal?: AbortSignal): Promise<Subscriber[]> {
  return (await getJson('/api/subscribers', z.object({ subscribers: z.array(subscriberSchema) }), signal)).subscribers
}

export function fetchNewsletterPreview(id: string, signal?: AbortSignal): Promise<NewsletterPreview> {
  return getJson(`/api/subscribers/${encodeURIComponent(id)}/preview`, newsletterPreviewSchema, signal)
}

const confirmationSchema = z.object({ sent: z.boolean(), error: z.string().nullable() })
const subscriberWithConfirmationSchema = subscriberSchema.extend({ confirmation: confirmationSchema })
export type SubscriberWithConfirmation = z.infer<typeof subscriberWithConfirmationSchema>
export type Confirmation = z.infer<typeof confirmationSchema>

export function createSubscriber(email: string): Promise<SubscriberWithConfirmation> {
  return request('/api/subscribers', subscriberWithConfirmationSchema, { method: 'POST', body: JSON.stringify({ email }) })
}

export function resendConfirmation(id: string): Promise<SubscriberWithConfirmation> {
  return request(`/api/subscribers/${encodeURIComponent(id)}/confirmation`, subscriberWithConfirmationSchema, { method: 'POST', body: '{}' })
}

export const deliveryKinds = ['confirmation', 'daily', 'weekly'] as const
const deliverySchema = z.object({
  id: z.number(),
  subscriber_id: z.string(),
  email: z.string(),
  kind: z.enum(deliveryKinds),
  subject: z.string(),
  /** The edition (daily) or the first day of the week (weekly). */
  reference: z.string().nullable(),
  status: z.enum(['sent', 'failed']),
  error: z.string().nullable(),
  created_at: z.string(),
})
export type Delivery = z.infer<typeof deliverySchema>

export async function fetchDeliveries(subscriberId?: string, signal?: AbortSignal): Promise<Delivery[]> {
  const path = subscriberId ? `/api/subscribers/${encodeURIComponent(subscriberId)}/deliveries?limit=30` : '/api/deliveries?limit=30'
  return (await getJson(path, z.object({ deliveries: z.array(deliverySchema) }), signal)).deliveries
}

export function updatePreferences(id: string, preferences: Preferences): Promise<Subscriber> {
  return request(`/api/subscribers/${encodeURIComponent(id)}`, subscriberSchema, {
    method: 'PUT',
    body: JSON.stringify({ preferences }),
  })
}

export function deleteSubscriber(id: string): Promise<{ deleted: string }> {
  return request(`/api/subscribers/${encodeURIComponent(id)}`, z.object({ deleted: z.string() }), {
    method: 'DELETE',
  })
}

// Quality evaluation (local-only routes, see lucidnews/evaluation/) ---------------------

export const annotationSchema = z.object({
  item_id: z.string(),
  relevant: z.boolean(),
  importance: z.enum(importanceLevels),
  categories: z.array(z.string()),
  claim_status: z.enum(claimStatuses),
  notes: z.string(),
  annotated_at: z.string(),
})

const evalItemSchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  source_type: z.string(),
  source: z.string(),
  author: z.string().nullable(),
  published_at: z.string(),
  excerpt: z.string(),
  discussion_url: z.string().nullable().optional(),
  annotation: annotationSchema.nullable(),
})

const rate = z.number().nullable()
const matrix = z.record(z.string(), z.record(z.string(), z.number()))

const comparisonSchema = z.object({
  item_id: z.string(),
  title: z.string(),
  issues: z.array(z.string()),
  human: z.object({
    relevant: z.boolean(),
    importance: z.string(),
    categories: z.array(z.string()),
    claim_status: z.string(),
    reliability: z.string().nullable(),
    notes: z.string(),
  }),
  ai: z.object({
    score: z.number().nullable(),
    selected: z.boolean(),
    importance: z.string().nullable(),
    categories: z.array(z.string()),
    claim_status: z.string().nullable(),
    reliability: z.string().nullable(),
  }),
})

export const reportSchema = z.object({
  annotated: z.number(),
  compared: z.number(),
  missing: z.array(z.string()),
  small_sample: z.boolean(),
  selection: z.object({
    true_positive: z.number(),
    false_positive: z.number(),
    false_negative: z.number(),
    true_negative: z.number(),
    precision: rate,
    recall: rate,
    f1: rate,
    accuracy: rate,
  }),
  importance: z.object({ exact: rate, within_one: rate, mean_band_error: rate, confusion: matrix }),
  categories: z.object({ precision: rate, recall: rate, f1: rate, exact_match: rate }),
  claim: z.object({ accuracy: rate, overconfident: z.number(), confusion: matrix }),
  reliability: z.object({ agreement: rate, false_reliable: z.number(), false_reliable_items: z.array(z.string()) }),
  items: z.array(comparisonSchema),
})

export type Annotation = z.infer<typeof annotationSchema>
export type AnnotationInput = Omit<Annotation, 'item_id' | 'annotated_at'>
export type EvalItem = z.infer<typeof evalItemSchema>
export type QualityReport = z.infer<typeof reportSchema>
export type Comparison = z.infer<typeof comparisonSchema>

export function fetchEvalItems(signal?: AbortSignal) {
  return getJson('/api/eval/items', z.object({ items: z.array(evalItemSchema), annotated: z.number() }), signal)
}

export function fetchQualityReport(signal?: AbortSignal): Promise<QualityReport> {
  return getJson('/api/eval/report', reportSchema, signal)
}

export function saveAnnotation(itemId: string, annotation: AnnotationInput): Promise<Annotation> {
  return request(`/api/eval/annotations/${encodeURIComponent(itemId)}`, annotationSchema, {
    method: 'PUT',
    body: JSON.stringify(annotation),
  })
}

export function deleteAnnotation(itemId: string): Promise<{ deleted: string }> {
  return request(`/api/eval/annotations/${encodeURIComponent(itemId)}`, z.object({ deleted: z.string() }), {
    method: 'DELETE',
  })
}

// Settings and API keys (local-only routes, see lucidnews/settings_api.py) ---------------

const settingsValuesSchema = z.object({
  ai: z.object({
    enabled: z.boolean(),
    provider: z.string(),
    model: z.string(),
    api_key_env: z.string(),
    languages: z.array(z.string()),
    max_requests_per_minute: z.number().nullable(),
    max_tokens_per_run: z.number().nullable(),
  }),
  collection: z.object({ time_window_hours: z.number() }),
  digest: z.object({
    max_items: z.number().nullable(),
    unanalyzed_max_items: z.number(),
    source_quality_days: z.number(),
  }),
  reliability: z.object({
    exclude_labels: z.array(z.enum(reliabilityLabels)),
    corroboration_lookback_hours: z.number(),
    corroboration_max_references: z.number(),
  }),
  archive: z.object({ reuse_analysis: z.boolean(), reuse_enrichment: z.boolean() }),
  profiles: z.record(z.string(), z.object({ threshold: z.number().nullable(), topic_dedup: z.boolean() })),
})

export const settingsSchema = z.object({
  version: z.string(),
  values: settingsValuesSchema,
  /** Fields set through a ${VARIABLE} in config.json: shown, not editable here. */
  locked: z.array(z.string()),
  options: z.object({
    providers: z.array(z.object({ id: z.string(), model: z.string(), api_key_env: z.string() })),
    languages: z.array(z.object({ code: z.string(), name: z.string() })),
    labels: z.array(z.enum(reliabilityLabels)),
    profiles: z.array(z.object({ id: z.string(), names: z.record(z.string(), z.string()) })),
  }),
})

const secretSchema = z.object({
  name: z.string(),
  used_by: z.array(z.string()),
  in_file: z.boolean(),
  in_environment: z.boolean(),
})

export type Settings = z.infer<typeof settingsSchema>
export type SettingsValues = z.infer<typeof settingsValuesSchema>
export type Secret = z.infer<typeof secretSchema>
export type Backup = { name: string; saved_at: string }

export function fetchSettings(signal?: AbortSignal): Promise<Settings> {
  return getJson('/api/settings', settingsSchema, signal)
}

export function saveSettings(version: string, values: SettingsValues): Promise<Settings> {
  return request('/api/settings', settingsSchema, { method: 'PUT', body: JSON.stringify({ version, values }) })
}

export async function fetchBackups(signal?: AbortSignal): Promise<Backup[]> {
  const schema = z.object({ backups: z.array(z.object({ name: z.string(), saved_at: z.string() })) })
  return (await getJson('/api/settings/backups', schema, signal)).backups
}

export function restoreBackup(name: string): Promise<Settings> {
  return request('/api/settings/restore', settingsSchema, { method: 'POST', body: JSON.stringify({ name }) })
}

export async function fetchSecrets(signal?: AbortSignal): Promise<Secret[]> {
  return (await getJson('/api/secrets', z.object({ secrets: z.array(secretSchema) }), signal)).secrets
}

// Sources: configuration (lot 17). Health stays in /api/sources.

const sourceEntrySchema = z.object({
  /** Same key as the health report, to join both. */
  key: z.string(),
  kind: z.string(),
  type: z.string(),
  label: z.string(),
  /** False for a built-in source whose section is not in config.json yet. */
  configured: z.boolean(),
  enabled: z.boolean(),
  /** False when the Reddit or Telegram switch pauses this source; null otherwise. */
  group_enabled: z.boolean().nullable(),
  values: z.record(z.string(), z.unknown()),
  summary: z.object({ mode: z.string(), users: z.number(), keywords: z.number() }).nullable(),
  locked: z.boolean(),
  readonly: z.boolean(),
  removable: z.boolean(),
  tracked: z.boolean(),
  group: z.boolean(),
})

export const sourceConfigSchema = z.object({
  version: z.string(),
  time_window_hours: z.number(),
  sources: z.array(sourceEntrySchema),
  kinds: z.array(z.object({ id: z.string(), type: z.string(), fields: z.array(z.string()), identity: z.array(z.string()) })),
  key: z.string().nullable().optional(),
})

export const sourceTestSchema = z.object({
  ok: z.boolean(),
  count: z.number(),
  in_window: z.number(),
  window_hours: z.number(),
  days: z.number(),
  error: z.string().nullable(),
  warnings: z.array(z.string()),
  duration_ms: z.number(),
  sample: z.array(z.object({ title: z.string(), url: z.string(), published_at: z.string() })),
})

export type SourceConfig = z.infer<typeof sourceConfigSchema>
export type SourceEntry = z.infer<typeof sourceEntrySchema>
export type SourceKind = SourceConfig['kinds'][number]
export type SourceTest = z.infer<typeof sourceTestSchema>
export type SourceValues = Record<string, unknown>

export function fetchSourceConfig(signal?: AbortSignal): Promise<SourceConfig> {
  return getJson('/api/sources/config', sourceConfigSchema, signal)
}

export function addSource(version: string, kind: string, values: SourceValues): Promise<SourceConfig> {
  return request('/api/sources/config', sourceConfigSchema, { method: 'POST', body: JSON.stringify({ version, kind, values }) })
}

export function updateSource(version: string, key: string, values: SourceValues): Promise<SourceConfig> {
  return request(`/api/sources/config/${encodeURIComponent(key)}`, sourceConfigSchema, {
    method: 'PUT',
    body: JSON.stringify({ version, values }),
  })
}

export function deleteSource(version: string, key: string): Promise<SourceConfig> {
  return request(`/api/sources/config/${encodeURIComponent(key)}`, sourceConfigSchema, {
    method: 'DELETE',
    body: JSON.stringify({ version }),
  })
}

/** A saved source by key, or a draft by kind and values. Nothing is written. */
export function testSource(body: { key: string } | { kind: string; values: SourceValues }): Promise<SourceTest> {
  return request('/api/sources/test', sourceTestSchema, { method: 'POST', body: JSON.stringify(body) })
}

// Domains: coverage of the 12 categories and recommended sources (lot 18).

export const coverageSchema = z.object({
  days: z.number(),
  watched: z.array(z.string()),
  only_watched: z.boolean(),
  min_sources: z.number(),
  min_items: z.number(),
  analyzed: z.number(),
  unanalyzed: z.number(),
  uncategorized: z.number(),
  categories: z.array(
    z.object({
      category: z.string(),
      watched: z.boolean(),
      gap: z.boolean(),
      gap_reasons: z.array(z.enum(['sources', 'items'])),
      items: z.number(),
      published: z.number(),
      active_sources: z.number(),
      sources: z.array(z.object({ source: z.string(), items: z.number(), configured: z.boolean() })),
      latest_at: z.string().nullable(),
      trusted_share: z.number().nullable(),
    }),
  ),
})

const catalogEntrySchema = z.object({
  key: z.string(),
  kind: z.string(),
  label: z.string(),
  category: z.string(),
  values: z.record(z.string(), z.unknown()),
  description: z.string().nullable(),
  origin: z.string(),
})

export type Coverage = z.infer<typeof coverageSchema>
export type DomainCoverage = Coverage['categories'][number]
export type CatalogEntry = z.infer<typeof catalogEntrySchema>

export function fetchCoverage(days: number, signal?: AbortSignal): Promise<Coverage> {
  return getJson(`/api/coverage?days=${days}`, coverageSchema, signal)
}

/** Recommended sources: catalog entries absent from the configuration. */
export async function fetchCatalog(signal?: AbortSignal): Promise<CatalogEntry[]> {
  return (await getJson('/api/catalog', z.object({ entries: z.array(catalogEntrySchema) }), signal)).entries
}

/** Some settings only; the others stay as they are in config.json. */
export function saveSomeSettings(version: string, values: Record<string, Record<string, unknown>>): Promise<Settings> {
  return request('/api/settings', settingsSchema, { method: 'PUT', body: JSON.stringify({ version, values }) })
}

// Quality of the watch: one page of indicators from the archive (lot 19).

const nullableCount = z.number().nullable()
const topSourceSchema = z.object({ source: z.string(), count: z.number(), share: z.number() }).nullable()

export const qualityOverviewSchema = z.object({
  days: z.number(),
  since: z.string(),
  runs: z.number(),
  published: z.number(),
  coverage: z.object({ watched: z.number(), gaps: z.array(z.string()), analyzed: z.number() }),
  diversity: z.object({
    active_sources: z.number(),
    configured_sources: z.number(),
    publishing_sources: z.number(),
    top_collected: topSourceSchema,
    top_published: topSourceSchema,
  }),
  health: z.object({
    by_status: z.record(z.enum(healthStatuses), z.number()),
    never_collected: z.number(),
    recent_errors: z.array(z.object({ source: z.string(), error: z.string().nullable(), at: z.string() })),
  }),
  freshness: z.object({
    items: z.number(),
    median_hours: nullableCount,
    p90_hours: nullableCount,
    within_24h: nullableCount,
  }),
  selection: z.object({
    runs_with_data: z.number(),
    runs_without_data: z.number(),
    fetched: nullableCount,
    url_merged: nullableCount,
    topic_merged: nullableCount,
    above_threshold: nullableCount,
    per_run: z.array(
      z.object({
        run_id: z.string(),
        started_at: z.string(),
        fetched: z.number(),
        selected: z.number(),
        url_merged: nullableCount,
        topic_merged: nullableCount,
        above_threshold: nullableCount,
      }),
    ),
  }),
  /** Hand evaluation summary; null where annotations are not available (non-local API). */
  filtering: z
    .object({
      annotated: z.number(),
      compared: z.number(),
      small_sample: z.boolean(),
      precision: nullableCount.optional(),
      recall: nullableCount.optional(),
      false_reliable: nullableCount.optional(),
      min_sample: z.number(),
    })
    .nullable(),
  reliability: z.object({
    labels: z.record(z.enum(reliabilityLabels), z.number()),
    unlabeled: z.number(),
    unanalyzed: z.number(),
  }),
})

export type QualityOverview = z.infer<typeof qualityOverviewSchema>

export function fetchQualityOverview(days: number, signal?: AbortSignal): Promise<QualityOverview> {
  return getJson(`/api/quality/overview?days=${days}`, qualityOverviewSchema, signal)
}

// Runs: start, follow, schedule (lot 20, local API only).

export const runSteps = ['fetch', 'analyze', 'select', 'write', 'done'] as const

export const runCurrentSchema = z.object({
  running: z.boolean(),
  origin: z.enum(['web', 'terminal', 'schedule']).nullable(),
  started_at: z.string().nullable(),
  step: z.enum(runSteps).nullable(),
  steps: z.array(z.string()),
  /** Exit code of the last run started from this page; null while running or for other origins. */
  exit_code: z.number().nullable(),
  already_running: z.boolean(),
  log: z.string(),
})

const historyRunSchema = runSchema.extend({
  status: z.string(),
  error: z.string().nullable(),
  unscored_count: z.number(),
})

export const scheduleSchema = z.object({
  supported: z.boolean(),
  enabled: z.boolean(),
  valid: z.boolean().optional(),
  loaded: z.boolean().optional(),
  hour: z.number().nullable().optional(),
  minute: z.number().nullable().optional(),
  weekdays: z.array(z.number()).optional(),
  next_run: z.string().nullable().optional(),
  label: z.string().optional(),
  log: z.string().optional(),
})

export type RunCurrent = z.infer<typeof runCurrentSchema>
export type HistoryRun = z.infer<typeof historyRunSchema>
export type Schedule = z.infer<typeof scheduleSchema>
export type RunStep = (typeof runSteps)[number]

export function fetchRunCurrent(signal?: AbortSignal): Promise<RunCurrent> {
  return getJson('/api/runs/current', runCurrentSchema, signal)
}

export function startRun(): Promise<RunCurrent> {
  return request('/api/runs', runCurrentSchema, { method: 'POST' })
}

export async function fetchRunHistory(signal?: AbortSignal): Promise<HistoryRun[]> {
  return (await getJson('/api/runs', z.object({ runs: z.array(historyRunSchema) }), signal)).runs
}

export function fetchSchedule(signal?: AbortSignal): Promise<Schedule> {
  return getJson('/api/schedule', scheduleSchema, signal)
}

export function saveSchedule(body: { enabled: false } | { enabled: true; hour: number; minute: number; weekdays: number[] }): Promise<Schedule> {
  return request('/api/schedule', scheduleSchema, { method: 'PUT', body: JSON.stringify(body) })
}

// Domain of each configured source (archive first, else the catalog) --------------------------

const sourceDomainSchema = z.object({
  category: z.string().nullable(),
  /** `archive`: categories of the news the source produced; `catalog`: declared by the catalog. */
  origin: z.enum(['archive', 'catalog']).nullable(),
  categories: z.array(z.object({ category: z.string(), items: z.number() })),
})
export type SourceDomain = z.infer<typeof sourceDomainSchema>

export async function fetchSourceDomains(signal?: AbortSignal): Promise<Record<string, SourceDomain>> {
  return (await getJson('/api/sources/domains?days=90', z.object({ domains: z.record(z.string(), sourceDomainSchema) }), signal)).domains
}

// Full-text search of the archive (lot 23) ------------------------------------------------------

const searchHitSchema = z.object({
  id: z.string(),
  title: z.string(),
  summary: z.string(),
  score: z.number().nullable(),
  reliability: z.enum(reliabilityLabels).nullable(),
  categories: z.array(z.string()),
  source: z.string(),
  source_type: z.string(),
  published_at: z.string(),
  /** Latest edition that published it; null when it was analyzed but never published. */
  edition: z.string().nullable(),
  edition_at: z.string().nullable(),
  unanalyzed: z.boolean(),
})

export const searchSchema = z.object({
  query: z.string(),
  terms: z.array(z.string()),
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
  /** Only the best matches are considered when a word matches a very large number of items. */
  truncated: z.boolean(),
  results: z.array(searchHitSchema),
  facets: z.object({
    categories: z.record(z.string(), z.number()),
    labels: z.record(z.string(), z.number()),
    sources: z.array(z.object({ source: z.string(), count: z.number() })),
  }),
})
export type SearchResult = z.infer<typeof searchSchema>
export type SearchHit = z.infer<typeof searchHitSchema>
export type SearchParams = { q: string; category?: string; label?: string; source?: string; offset?: number }
export const SEARCH_PAGE_SIZE = 30
export const SEARCH_MAX_QUERY = 200

export function fetchSearch(params: SearchParams, language: string, signal?: AbortSignal): Promise<SearchResult> {
  const query = new URLSearchParams({ q: params.q, lang: language, limit: String(SEARCH_PAGE_SIZE) })
  for (const key of ['category', 'label', 'source'] as const) if (params[key]) query.set(key, params[key])
  if (params.offset) query.set('offset', String(params.offset))
  return getJson(`/api/search?${query}`, searchSchema, signal)
}

// Accounts (see lucidnews/auth). With auth.enabled off the API answers {enabled: false}.

export const authUserSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
  picture: z.string().nullable(),
  has_password: z.boolean(),
  has_google: z.boolean(),
  /** admin: runs the newsroom (sources, quality, subscribers, settings); reader: reads the news. */
  role: z.enum(['admin', 'reader']),
})

export const sessionSchema = z.object({
  enabled: z.boolean(),
  authenticated: z.boolean(),
  user: authUserSchema.nullable(),
  signup_enabled: z.boolean(),
  providers: z.object({ google: z.boolean() }),
})

export type AuthUser = z.infer<typeof authUserSchema>
export type Session = z.infer<typeof sessionSchema>

const NO_ACCOUNTS: Session = { enabled: false, authenticated: false, user: null, signup_enabled: false, providers: { google: false } }

/** An API without accounts (older, or auth.enabled off) answers 404 or {enabled: false}: the app stays open. */
export async function fetchSession(signal?: AbortSignal): Promise<Session> {
  try {
    return await getJson('/api/auth/session', sessionSchema, signal)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return NO_ACCOUNTS
    throw error
  }
}

export function signIn(email: string, password: string): Promise<Session> {
  return request('/api/auth/sign-in', sessionSchema, { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function signUp(email: string, password: string, name: string): Promise<Session> {
  return request('/api/auth/sign-up', sessionSchema, { method: 'POST', body: JSON.stringify({ email, password, name }) })
}

export function signOut(): Promise<Session> {
  return request('/api/auth/sign-out', sessionSchema, { method: 'POST', body: JSON.stringify({}) })
}
