import { apiRequest } from "@/lib/api"

export interface FieldOption {
  value: string
  label: string
}

export interface ModelField {
  key: string
  kind: "bool" | "number" | "select"
  label: string
  group: string
  unit?: string
  min?: number
  max?: number
  step?: number
  options?: FieldOption[]
  help?: string
}

export interface RocCurve {
  fpr: number[]
  tpr: number[]
}

export interface ModelMetrics {
  cutoff_test_year: number
  n_train: number
  n_test: number
  base_rate: number
  auc_roc: number
  auc_pr: number
  brier: number
  cv_auc_roc_mean: number
  youden_threshold: number
  roc_curve?: RocCurve
}

export interface OddsRatio {
  feature: string
  odds_ratio: number
}

export interface ModelInfo {
  cohort: string
  title: string
  description: string
  available: boolean
  features: ModelField[]
  version?: string
  trained_at?: string
  n_samples?: number
  n_deaths?: number
  outcome?: string
  target?: string
  base_rate?: number
  metrics?: ModelMetrics
  odds_ratios?: OddsRatio[]
}

export interface ContributingFactor {
  factor: string
  odds_ratio: number
}

export interface ExplanationItem {
  label: string
  effect: number
  direction: "up" | "down"
}

export interface PredictionResult {
  cohort: string
  probability: number
  probability_pct: number
  risk_level: "bajo" | "moderado" | "alto"
  threshold: number
  base_rate: number
  risk_ratio?: number | null
  contributing_factors: ContributingFactor[]
  explanation: ExplanationItem[]
  model_version?: string | null
}

export function listModels() {
  return apiRequest<ModelInfo[]>("/predictions/models", { method: "GET" })
}

export function predict(cohort: string, values: Record<string, unknown>) {
  return apiRequest<PredictionResult>(`/predictions/${cohort}`, {
    method: "POST",
    body: { values },
  })
}
