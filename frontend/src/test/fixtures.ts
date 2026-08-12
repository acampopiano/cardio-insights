import type { ModelInfo, PredictionResult } from "@/features/predictions/predictionsApi"

export const mockModelPtca: ModelInfo = {
  cohort: "ptca",
  title: "PTCA / angioplastia",
  description: "Riesgo de mortalidad en PTCA",
  available: true,
  outcome: "mortalidad",
  target: "IPfallece",
  n_samples: 1000,
  n_deaths: 40,
  base_rate: 0.04,
  features: [
    {
      key: "edad",
      kind: "number",
      label: "Edad",
      group: "Demograficos",
      unit: "años",
      min: 18,
      max: 100,
      step: 1,
    },
    {
      key: "diabetes",
      kind: "bool",
      label: "Diabetes",
      group: "Riesgo",
    },
    {
      key: "clase_nyha",
      kind: "select",
      label: "Clase NYHA",
      group: "Clinico",
      options: [
        { value: "1", label: "I" },
        { value: "2", label: "II" },
      ],
    },
  ],
  metrics: {
    cutoff_test_year: 2023,
    n_train: 800,
    n_test: 200,
    base_rate: 0.04,
    auc_roc: 0.82,
    auc_pr: 0.2,
    brier: 0.03,
    cv_auc_roc_mean: 0.8,
    youden_threshold: 0.1,
    roc_curve: {
      fpr: [0, 0.2, 0.5, 1],
      tpr: [0, 0.6, 0.85, 1],
    },
  },
  odds_ratios: [
    { feature: "num__edad", odds_ratio: 1.8 },
    { feature: "bin__diabetes", odds_ratio: 1.4 },
    { feature: "cat__clase_nyha_2", odds_ratio: 1.6 },
    { feature: "num__otro", odds_ratio: 0.7 },
    { feature: "unknown_feat", odds_ratio: 0.5 },
  ],
}

export const mockModelSurgery: ModelInfo = {
  cohort: "cirugia",
  title: "Cirugia cardiaca",
  description: "Mortalidad a 30 dias",
  available: true,
  outcome: "mortalidad a 30 dias",
  target: "fallece_30d",
  n_samples: 500,
  n_deaths: 30,
  features: [
    {
      key: "euroscore",
      kind: "number",
      label: "EuroSCORE",
      group: "Scores",
    },
  ],
  metrics: {
    cutoff_test_year: 2022,
    n_train: 400,
    n_test: 100,
    base_rate: 0.06,
    auc_roc: 0.76,
    auc_pr: 0.15,
    brier: 0.05,
    cv_auc_roc_mean: 0.74,
    youden_threshold: 0.12,
  },
  odds_ratios: [{ feature: "num__euroscore", odds_ratio: 2.1 }],
}

export const mockModelUnavailable: ModelInfo = {
  cohort: "legacy",
  title: "Legacy",
  description: "No disponible",
  available: false,
  features: [],
}

export const mockPrediction: PredictionResult = {
  cohort: "ptca",
  probability: 0.12,
  probability_pct: 12,
  risk_level: "alto",
  threshold: 0.1,
  base_rate: 0.04,
  risk_ratio: 3,
  contributing_factors: [{ factor: "edad", odds_ratio: 1.8 }],
  explanation: [
    { label: "Edad", effect: 0.9, direction: "up" },
    { label: "Diabetes", effect: 0.4, direction: "up" },
    { label: "NYHA I", effect: -0.2, direction: "down" },
  ],
  model_version: "1.0",
}
