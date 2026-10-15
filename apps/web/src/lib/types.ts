export type Article = {
  id: string | null;
  title: string | null;
  text: string | null;
  source: string | null;
  source_type: string | null;
  url: string | null;
  published_at: string | null;
  read_error?: string | null;
  original_record?: Record<string, unknown> | null;
};
export type Evidence = {
  fragment: string;
  source_id: string;
  url?: string | null;
};
export type RewrittenCopy = {
  events: {
    event_id: string;
    digest: { text: string; evidence: Evidence[] }[];
    post: { text: string; evidence: Evidence[] }[];
  }[];
};
export type DigestEvent = {
  event_id: string;
  title: string;
  summary: string;
  consequences: string;
  affected_entities: string[];
  affected_systems: string[];
  reported_by: string[];
  confidence: string;
  is_preliminary: boolean;
  conflicts: string[];
  source_ids: string[];
  primary_source_id: string | null;
  selection_reason: string;
  ranking_factors: Record<string, number>;
  evidence: Evidence[];
};
export type JournalRow = {
  source_index?: number;
  original_record?: Record<string, unknown>;
  normalized_record?: Article | null;
  evidence?: Evidence[];
  related_sources?: string[];
  id: string | null;
  title: string | null;
  source: string | null;
  source_type: string | null;
  url: string | null;
  published_at: string | null;
  status: string;
  event_id: string | null;
  inclusion_reason: string | null;
  exclusion_reason: string | null;
  missing_fields: string[];
  errors: string[];
  warnings: string[];
  relevance: unknown;
  period_check: unknown;
  fact_check: unknown;
  model_name: string;
  prompt_version: string;
  processed_at: string;
};
export type DigestResult = {
  digest_id: string;
  period_start: string;
  period_end: string;
  control_time: string;
  timezone: string;
  events: DigestEvent[];
  event_count: number;
  digest_text: string;
  email_subject: string;
  email_preview_html: string;
  post_text: string;
  warnings: string[];
  sources: Article[];
  journal: JournalRow[];
  checks: { name: string; passed: boolean; details: unknown }[];
  metrics: Record<string, unknown>;
  model_name: string;
  model_version: string;
  prompt_version: string;
  created_at: string;
  editorial_plan?: unknown | null;
  ai_copy?: RewrittenCopy | null;
  mode?: "ai" | "mock" | "fallback";
  llm_attempts?: number;
  token_usage?: {
    input: number | null;
    output: number | null;
    total: number | null;
  };
  started_at?: string;
  completed_at?: string;
  application_version?: string;
};
export type AIExecutionStamp = {
  mode: "ai" | "fallback";
  model_name: string;
  prompt_version: string;
  completed_at: string;
  application_version: string;
};
export type Health = {
  status: string;
  mode: string;
  model_name: string;
  prompt_version: string;
  llm_configured?: boolean;
  execution_status?: {
    last_ai_run: AIExecutionStamp | null;
    last_successful_ai_run: AIExecutionStamp | null;
  };
};
