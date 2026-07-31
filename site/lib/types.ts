/** Shapes written by `ragarena bench`. Mirrors ragarena/types.py. */

export type Metrics = Record<string, number>;

export interface LatencyStats {
  mean_ms: number;
  p50_ms: number;
  p90_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  embed_tokens: number;
  rerank_tokens: number;
  llm_calls: number;
  embed_calls: number;
  rerank_calls: number;
}

export interface Cost {
  llm_usd: number;
  embed_usd: number;
  rerank_usd: number;
}

export interface RetrievedChunk {
  chunk_id: string;
  doc_id: string;
  text: string;
  rank: number;
  score: number;
  dense_score: number | null;
  lexical_score: number | null;
  fused_score: number | null;
  rerank_score: number | null;
  title: string;
}

export interface Answer {
  text: string;
  citations: number[];
  abstained: boolean;
}

export interface QueryTrace {
  question_id: string;
  question: string;
  answerable: boolean;
  ground_truth: string | null;
  retrieved: RetrievedChunk[];
  answer: Answer | null;
  scores: Metrics;
  judge_notes: Record<string, string>;
  usage: Usage;
  cost: Cost;
  timings: {
    embed_query_ms: number;
    retrieve_ms: number;
    rerank_ms: number;
    generate_ms: number;
    total_ms: number;
  };
  error: string | null;
  cached: boolean;
}

export interface StrategyResult {
  name: string;
  label: string;
  description: string;
  config: Record<string, string | number | boolean>;
  metrics: Metrics;
  metrics_by_segment: Record<string, Metrics>;
  latency: LatencyStats;
  stage_latency: Record<string, number>;
  usage: Usage;
  cost: Cost;
  cost_per_1k_queries_usd: number;
  cost_per_1k_queries_uncached_usd: number;
  eval_cost_usd: number;
  index_build_ms: number;
  n_chunks: number;
  n_questions: number;
  n_errors: number;
  traces: QueryTrace[];
}

export interface DatasetInfo {
  name: string;
  description: string;
  version: string;
  n_documents: number;
  n_questions: number;
  total_words: number;
  question_types: Record<string, number>;
}

export interface RunEnvironment {
  ragarena_version: string;
  python_version: string;
  platform: string;
  concurrency: number;
  index_backend: string;
  generator_model: string;
  judge_model: string;
  embed_provider: string;
  embed_model: string;
  rerank_provider: string;
  rerank_model: string;
}

export interface RunSummary {
  run_id: string;
  created_at: string;
  duration_s: number;
  primary_metric: string;
  notes: string;
  dataset: DatasetInfo;
  environment: RunEnvironment;
  arena_weights: Record<string, number>;
  metric_order: string[];
  winner: string;
  strategies: StrategyResult[];
}

export interface RunIndexEntry {
  run_id: string;
  created_at: string;
  duration_s: number;
  notes: string;
  primary_metric: string;
  dataset: string;
  dataset_version: string;
  n_documents: number;
  n_questions: number;
  n_strategies: number;
  generator_model: string;
  judge_model: string;
  embed_model: string;
  rerank_model: string;
  winner: string;
  winner_label: string;
  winner_score: number;
  summary: string;
}
