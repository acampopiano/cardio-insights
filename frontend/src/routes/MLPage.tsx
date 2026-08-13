import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BookOpen,
  Brain,
  HelpCircle,
  Loader2,
  Stethoscope,
} from "lucide-react"

import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import {
  listModels,
  predict,
  type ModelField,
  type ModelInfo,
  type PredictionResult,
} from "@/features/predictions/predictionsApi"

type Values = Record<string, unknown>

function initialValues(model: ModelInfo): Values {
  const v: Values = {}
  for (const f of model.features) {
    if (f.kind === "bool") v[f.key] = false
    else v[f.key] = ""
  }
  return v
}

const RISK_STYLES: Record<
  string,
  { label: string; bar: string; text: string; bg: string; meaning: string }
> = {
  bajo: {
    label: "Riesgo bajo",
    bar: "bg-emerald-500",
    text: "text-emerald-700 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    meaning: "Por debajo del promedio de pacientes similares.",
  },
  moderado: {
    label: "Riesgo moderado",
    bar: "bg-amber-500",
    text: "text-amber-700 dark:text-amber-400",
    bg: "bg-amber-500/10",
    meaning: "Por encima del promedio, sin superar el umbral de alerta del modelo.",
  },
  alto: {
    label: "Riesgo alto",
    bar: "bg-red-500",
    text: "text-red-700 dark:text-red-400",
    bg: "bg-red-500/10",
    meaning: "Supera el umbral de alerta del modelo. Requiere atención, no es un pronóstico definitivo.",
  },
}

const METRIC_HELP: Record<string, string> = {
  auc: "AUC-ROC: capacidad de ordenar bien a quién tiene más riesgo (0.5 = azar, 1.0 = perfecto).",
  aucpr: "AUC-PR: precisión al detectar los casos positivos (poco frecuentes). Se compara contra el azar.",
  brier: "Brier: qué tan calibradas están las probabilidades (más bajo = mejor).",
}

export function MLPage() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [cohort, setCohort] = useState<string>("")
  const [values, setValues] = useState<Values>({})
  const [result, setResult] = useState<PredictionResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingModels, setLoadingModels] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listModels()
      .then((data) => {
        setModels(data)
        const first = data.find((m) => m.available) ?? data[0]
        if (first) {
          setCohort(first.cohort)
          setValues(initialValues(first))
        }
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudieron cargar los modelos.")
      )
      .finally(() => setLoadingModels(false))
  }, [])

  const model = useMemo(() => models.find((m) => m.cohort === cohort), [models, cohort])

  const groups = useMemo(() => {
    if (!model) return []
    const order: string[] = []
    const byGroup: Record<string, ModelField[]> = {}
    for (const f of model.features) {
      if (!byGroup[f.group]) {
        byGroup[f.group] = []
        order.push(f.group)
      }
      byGroup[f.group].push(f)
    }
    return order.map((g) => ({ group: g, fields: byGroup[g] }))
  }, [model])

  function selectCohort(next: string) {
    setCohort(next)
    setResult(null)
    setError(null)
    const m = models.find((x) => x.cohort === next)
    if (m) setValues(initialValues(m))
  }

  function setValue(key: string, value: unknown) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  async function onSubmit() {
    if (!model || loading) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await predict(model.cohort, values)
      setResult(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo calcular la predicción.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageShell>
      <header className="mb-6 flex items-center gap-3">
        <div className="grid size-11 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]">
          <Brain className="size-6" />
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-semibold">Predicciones ML</h1>
          <p className="text-sm text-muted-foreground">
            Estimá el riesgo de un procedimiento (mortalidad o complicaciones) a partir de
            variables clínicas.
          </p>
        </div>
        <Link
          to="/ml/metodologia"
          className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <BookOpen className="size-4" />
          Metodología
        </Link>
      </header>

      <p className="mb-5 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
        <span>
          Herramienta de <strong>apoyo e investigación</strong>, no un sistema de decisión clínica.
          Las estimaciones surgen de modelos estadísticos sobre datos históricos del INCC y no
          reemplazan el juicio médico.
        </span>
      </p>

      {loadingModels ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Cargando modelos…
        </div>
      ) : error && models.length === 0 ? (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
          <p className="mt-2 text-muted-foreground">
            Verificá que el API esté corriendo y que hayas iniciado sesión.
          </p>
        </div>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap gap-2">
            {models.map((m) => {
              const active = m.cohort === cohort
              const Icon = m.cohort === "ptca" ? Activity : Stethoscope
              return (
                <button
                  key={m.cohort}
                  type="button"
                  onClick={() => selectCohort(m.cohort)}
                  disabled={!m.available}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-4 py-2 text-sm transition-colors",
                    active
                      ? "border-[var(--color-incc-primary)] bg-[var(--color-incc-primary)]/10 text-foreground"
                      : "bg-background text-muted-foreground hover:text-foreground",
                    !m.available && "cursor-not-allowed opacity-50"
                  )}
                >
                  <Icon className="size-4" />
                  {m.title}
                  {!m.available && <span className="text-xs">(no disponible)</span>}
                </button>
              )
            })}
          </div>

          {models.length === 0 && !error && (
            <p className="text-sm text-muted-foreground">No hay modelos disponibles.</p>
          )}

          {model && (
            <div className="grid gap-6 lg:grid-cols-[1fr_420px] lg:items-start">
              {/* Formulario */}
              <Card>
                <CardHeader className="border-b">
                  <CardTitle>{model.title}</CardTitle>
                  <CardDescription>{model.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6 pt-6">
                  {groups.map(({ group, fields }) => (
                    <fieldset key={group} className="space-y-3">
                      <legend className="text-sm font-medium text-foreground">{group}</legend>
                      <div className="grid gap-3 sm:grid-cols-2">
                        {fields.map((f) => (
                          <FieldInput
                            key={f.key}
                            field={f}
                            value={values[f.key]}
                            onChange={(v) => setValue(f.key, v)}
                          />
                        ))}
                      </div>
                    </fieldset>
                  ))}

                  <div className="flex items-center gap-3 pt-2">
                    <Button onClick={onSubmit} disabled={loading} size="lg">
                      {loading ? <Loader2 className="size-4 animate-spin" /> : <Brain className="size-4" />}
                      Calcular riesgo
                    </Button>
                    {error && <p className="text-sm text-destructive">{error}</p>}
                  </div>
                </CardContent>
              </Card>

              {/* Resultado */}
              <div className="space-y-4 lg:sticky lg:top-6">
                <ResultPanel result={result} loading={loading} outcome={model.outcome ?? "mortalidad"} />
                <HowToRead outcome={model.outcome ?? "mortalidad"} />
                <ModelInfoCard model={model} />
              </div>
            </div>
          )}
        </>
      )}
    </PageShell>
  )
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: ModelField
  value: unknown
  onChange: (value: unknown) => void
}) {
  if (field.kind === "bool") {
    return (
      <label className="flex cursor-pointer items-center gap-2 rounded-lg border bg-background px-3 py-2 text-sm">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
          className="size-4 accent-[var(--color-incc-primary)]"
        />
        <span>{field.label}</span>
      </label>
    )
  }

  if (field.kind === "select") {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={field.key}>{field.label}</Label>
        <select
          id={field.key}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <option value="">Sin especificar</option>
          {field.options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={field.key}>
        {field.label}
        {field.unit && <span className="ml-1 text-xs text-muted-foreground">({field.unit})</span>}
      </Label>
      <Input
        id={field.key}
        type="number"
        inputMode="decimal"
        min={field.min}
        max={field.max}
        step={field.step}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder="—"
      />
    </div>
  )
}

function ResultPanel({
  result,
  loading,
  outcome,
}: {
  result: PredictionResult | null
  loading: boolean
  outcome: string
}) {
  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Calculando…
        </CardContent>
      </Card>
    )
  }

  if (!result) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          Completá los datos y presioná <strong>Calcular riesgo</strong> para ver la estimación.
        </CardContent>
      </Card>
    )
  }

  const style = RISK_STYLES[result.risk_level] ?? RISK_STYLES.moderado
  const width = Math.min(100, Math.max(2, result.probability_pct))
  const ratio = result.risk_ratio ?? null
  const maxEffect = Math.max(...result.explanation.map((e) => Math.abs(e.effect)), 0.0001)

  return (
    <Card className={cn("border-2", style.bg)}>
      <CardHeader className="border-b">
        <CardDescription>Probabilidad estimada de {outcome}</CardDescription>
        <CardTitle className="text-3xl font-bold">{result.probability_pct.toFixed(1)}%</CardTitle>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span className={cn("inline-flex w-fit rounded-full px-2.5 py-0.5 text-xs font-medium", style.bg, style.text)}>
            {style.label}
          </span>
          {ratio !== null && (
            <span className="text-xs text-muted-foreground">
              ≈ {ratio}× el promedio ({(result.base_rate * 100).toFixed(1)}%)
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{style.meaning}</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        <div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div className={cn("h-full rounded-full transition-all", style.bar)} style={{ width: `${width}%` }} />
          </div>
          <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
            <span>Promedio: {(result.base_rate * 100).toFixed(1)}%</span>
            <span>Umbral de alerta: {(result.threshold * 100).toFixed(1)}%</span>
          </div>
        </div>

        {result.explanation.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">¿Qué pesó en esta estimación?</p>
            <p className="text-xs text-muted-foreground">
              Cada barra muestra cuánto influye cada dato de este paciente:{" "}
              <span className="text-red-600">sube</span> o{" "}
              <span className="text-emerald-600">baja</span> el riesgo.
            </p>
            <ul className="space-y-1.5">
              {result.explanation.map((e) => {
                const up = e.direction === "up"
                const ratio = Math.abs(e.effect) / maxEffect
                const w = Math.max(6, ratio * 100)
                const strength =
                  ratio >= 0.66 ? "Fuerte" : ratio >= 0.33 ? "Medio" : "Leve"
                const tip = `${up ? "Sube" : "Baja"} el riesgo · impacto ${strength.toLowerCase()}`
                return (
                  <li key={e.label} className="flex items-center gap-2 text-sm" title={tip}>
                    {up ? (
                      <ArrowUp className="size-3.5 shrink-0 text-red-500" />
                    ) : (
                      <ArrowDown className="size-3.5 shrink-0 text-emerald-500" />
                    )}
                    <span className="w-40 shrink-0 truncate text-muted-foreground">
                      {e.label}
                    </span>
                    <span className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                      <span
                        className={cn("block h-full rounded-full", up ? "bg-red-500" : "bg-emerald-500")}
                        style={{ width: `${w}%` }}
                      />
                    </span>
                    <span className="w-12 shrink-0 text-right text-xs text-muted-foreground">
                      {strength}
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function reliability(auc: number): { word: string; cls: string } {
  if (auc >= 0.8) return { word: "Muy buena", cls: "text-emerald-700 dark:text-emerald-400" }
  if (auc >= 0.75) return { word: "Buena", cls: "text-emerald-700 dark:text-emerald-400" }
  if (auc >= 0.7) return { word: "Aceptable", cls: "text-amber-700 dark:text-amber-400" }
  return { word: "Limitada", cls: "text-amber-700 dark:text-amber-400" }
}

function ModelInfoCard({ model }: { model: ModelInfo }) {
  const m = model.metrics
  if (!m) return null
  const rel = reliability(m.auc_roc)
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-sm">Sobre el modelo</CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 pt-4 text-sm">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1 text-muted-foreground">
            Confiabilidad
            <span
              title="Qué tan bien distingue el modelo a los pacientes de mayor riesgo, medido sobre casos que no usó para aprender."
              className="cursor-help"
            >
              <HelpCircle className="size-3 opacity-60" />
            </span>
          </span>
          <span className={cn("font-semibold", rel.cls)}>{rel.word}</span>
        </div>
        <Row label="Casos analizados" value={(model.n_samples ?? 0).toLocaleString()} />
        <Row label="Casos con el evento" value={(model.n_deaths ?? 0).toLocaleString()} />
        <p className="pt-1 text-xs text-muted-foreground">
          Aprendido de datos históricos del INCC. Las probabilidades están calibradas para
          reflejar la frecuencia real observada.
        </p>
        <details className="group pt-1">
          <summary className="cursor-pointer list-none text-xs text-[var(--color-incc-primary)]">
            Ver detalle técnico
          </summary>
          <div className="mt-2 space-y-1.5">
            <Row label="AUC-ROC (validación)" value={m.auc_roc.toFixed(3)} help={METRIC_HELP.auc} />
            <Row label="AUC-PR" value={`${m.auc_pr.toFixed(3)} (azar ${m.base_rate.toFixed(3)})`} help={METRIC_HELP.aucpr} />
            <Row label="Brier (calibración)" value={m.brier.toFixed(3)} help={METRIC_HELP.brier} />
            <p className="text-xs text-muted-foreground">
              Regresión logística calibrada, validación temporal. Objetivo: {model.target}.
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  )
}

function Row({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-1 text-muted-foreground">
        {label}
        {help && (
          <span title={help} className="cursor-help">
            <HelpCircle className="size-3 opacity-60" />
          </span>
        )}
      </span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

function HowToRead({ outcome }: { outcome: string }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <details className="group">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium">
            <HelpCircle className="size-4 text-[var(--color-incc-primary)]" />
            ¿Cómo leer esta estimación?
          </summary>
          <div className="mt-3 space-y-2 text-xs text-muted-foreground">
            <p>
              <strong>Probabilidad</strong>: chance estimada de {outcome} para un paciente con
              estas características, según los datos históricos del INCC.
            </p>
            <p>
              <strong>× el promedio</strong>: cuántas veces por encima (o por debajo) del promedio
              de pacientes similares. Comunica el riesgo <em>relativo</em>.
            </p>
            <p>
              <strong>Nivel de riesgo</strong>: bajo / moderado / alto. "Alto" señala que conviene
              revisar el caso, <em>no</em> es un pronóstico definitivo.
            </p>
            <p>
              <strong>Barras "¿qué pesó?"</strong>: cuánto influye cada dato de este paciente
              (rojo = sube el riesgo, verde = lo baja; la longitud indica cuánto).
            </p>
            <p className="text-amber-700 dark:text-amber-500">
              El modelo es una ayuda estadística; no reemplaza la evaluación clínica ni considera
              variables no registradas.
            </p>
          </div>
        </details>
      </CardContent>
    </Card>
  )
}
