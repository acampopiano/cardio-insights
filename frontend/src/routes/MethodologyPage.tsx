import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, BookOpen, Loader2 } from "lucide-react"

import { PageShell } from "@/components/layout/PageShell"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ApiError } from "@/lib/api"
import { listModels, type ModelInfo, type RocCurve } from "@/features/predictions/predictionsApi"

export function MethodologyPage() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "No se pudieron cargar los modelos.")
      )
      .finally(() => setLoading(false))
  }, [])

  const available = models.filter((m) => m.available && m.metrics)

  return (
    <PageShell>
      <Link
        to="/ml"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Volver a Predicciones ML
      </Link>

      <header className="mb-6 flex items-center gap-3">
        <div className="grid size-11 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]">
          <BookOpen className="size-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Metodología de los modelos</h1>
          <p className="text-sm text-muted-foreground">
            Cómo se construyeron, validaron y qué limitaciones tienen los modelos predictivos.
          </p>
        </div>
      </header>

      <p className="mb-6 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
        <span>
          Estas herramientas son de <strong>apoyo e investigación</strong>. No constituyen un
          sistema de decisión clínica ni reemplazan el juicio del equipo médico.
        </span>
      </p>

      <div className="space-y-4">
        <Section title="1. Origen de los datos">
          <p>
            Los modelos se entrenaron sobre la base de datos histórica del <strong>Instituto
            Nacional de Cirugía Cardíaca (INCC)</strong>. Se usan únicamente registros de
            procedimientos efectivamente realizados (fecha válida), excluyendo los nulos lógicos
            (fechas <code>≤ 1900-01-01</code>).
          </p>
        </Section>

        <Section title="2. Qué se predice">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong>PTCA / angioplastia</strong>: mortalidad asociada al procedimiento, tomada
              del propio formulario (<code>IPfallece</code> / <code>PPfallece</code>).
            </li>
            <li>
              <strong>Cirugía cardíaca (mortalidad)</strong>: mortalidad a <strong>30 días</strong>,
              cruzando con el registro de fallecimientos <code>sqlsalud_fallece</code> (fecha de
              muerte real). Usa el registro reciente (2021 en adelante), que incorpora el{" "}
              <strong>EuroSCORE</strong> (score internacional de riesgo quirúrgico) como variable
              opcional de alto valor predictivo.
            </li>
            <li>
              <strong>Complicaciones graves de cirugía</strong>: presencia de al menos una
              complicación grave intrahospitalaria (falla renal, hemodiálisis, sangrado quirúrgico,
              resutura o dehiscencia). Registrado 2008–2022, por lo que el modelo se entrena con esa
              ventana.
            </li>
          </ul>
        </Section>

        <Section title="3. Variables y regla anti-fuga (leakage)">
          <p>
            Se usan solo variables <strong>conocidas antes del procedimiento</strong>: factores de
            riesgo, comorbilidades, cuadro clínico de entrada, función cardíaca y tipo de cirugía.
            Se <strong>excluyen deliberadamente</strong> todas las variables intra y
            postoperatorias (complicaciones, tiempos de CEC, estadía en UCI), porque usarlas
            "haría trampa": no estarían disponibles en el momento en que la predicción sería útil.
          </p>
          {!loading && !error && available.length > 0 && (
            <div className="space-y-4 pt-1">
              <p className="text-xs text-muted-foreground">
                Variables efectivamente usadas por cada modelo:
              </p>
              {available.map((m) => (
                <VariablesBlock key={m.cohort} model={m} />
              ))}
            </div>
          )}
        </Section>

        <Section title="4. Modelo y validación">
          <p>
            Se emplea <strong>regresión logística</strong> con balanceo de clases y{" "}
            <strong>calibración</strong> (Platt), de modo que las probabilidades reflejen la
            frecuencia real observada. La validación es <strong>temporal</strong>: se entrena con
            los años más antiguos y se evalúa con los más recientes, simulando el uso real (predecir
            el futuro con datos del pasado) en lugar de un split aleatorio optimista.
          </p>
        </Section>

        <Section title="5. Métricas (validación temporal)">
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Cargando métricas…
            </div>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Modelo</th>
                    <th className="py-2 pr-3 font-medium">Casos</th>
                    <th className="py-2 pr-3 font-medium">Eventos</th>
                    <th className="py-2 pr-3 font-medium">AUC-ROC</th>
                    <th className="py-2 pr-3 font-medium">AUC-PR</th>
                    <th className="py-2 pr-3 font-medium">Brier</th>
                    <th className="py-2 font-medium">Test desde</th>
                  </tr>
                </thead>
                <tbody>
                  {available.map((m) => (
                    <tr key={m.cohort} className="border-b last:border-0">
                      <td className="py-2 pr-3">{m.title}</td>
                      <td className="py-2 pr-3 tabular-nums">{(m.n_samples ?? 0).toLocaleString()}</td>
                      <td className="py-2 pr-3 tabular-nums">{(m.n_deaths ?? 0).toLocaleString()}</td>
                      <td className="py-2 pr-3 tabular-nums">{m.metrics!.auc_roc.toFixed(3)}</td>
                      <td className="py-2 pr-3 tabular-nums">{m.metrics!.auc_pr.toFixed(3)}</td>
                      <td className="py-2 pr-3 tabular-nums">{m.metrics!.brier.toFixed(3)}</td>
                      <td className="py-2 tabular-nums">{m.metrics!.cutoff_test_year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <dl className="mt-3 space-y-1 text-xs text-muted-foreground">
                <div><strong>AUC-ROC</strong>: capacidad de ordenar el riesgo (0.5 = azar, 1.0 = perfecto).</div>
                <div><strong>AUC-PR</strong>: detección de los casos positivos (poco frecuentes) vs. el azar.</div>
                <div><strong>Brier</strong>: calibración de las probabilidades (más bajo = mejor).</div>
              </dl>

              {available.some((m) => m.metrics?.roc_curve) && (
                <div className="mt-5">
                  <p className="mb-1 text-sm font-medium">Curvas ROC</p>
                  <p className="mb-3 text-xs text-muted-foreground">
                    Muestran el equilibrio entre detectar los casos de riesgo (eje vertical) y las
                    falsas alarmas (eje horizontal). Cuanto más se despega la curva de la diagonal
                    (azar), mejor. El área bajo la curva es el AUC-ROC.
                  </p>
                  <div className="flex flex-wrap gap-6">
                    {available
                      .filter((m) => m.metrics?.roc_curve)
                      .map((m) => (
                        <RocChart
                          key={m.cohort}
                          title={m.title}
                          auc={m.metrics!.auc_roc}
                          curve={m.metrics!.roc_curve!}
                        />
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Section>

        <Section title="6. Factores más influyentes">
          <p>
            El modelo, al entrenarse, aprende qué características se asocian con mayor o menor
            mortalidad. Estos son los factores con más peso en cada modelo (asociaciones
            estadísticas ajustadas por el resto de las variables; no implican causalidad).
          </p>
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Cargando factores…
            </div>
          ) : error ? (
            <p className="text-destructive">{error}</p>
          ) : (
            <div className="space-y-4 pt-1">
              {available.map((m) => (
                <FactorsBlock key={m.cohort} model={m} />
              ))}
            </div>
          )}
        </Section>

        <Section title="7. Explicabilidad">
          <p>
            Para cada predicción se muestra la <strong>contribución de cada variable</strong>
            (descomposición en log-odds del modelo lineal, equivalente a valores SHAP exactos):
            cuánto empuja el riesgo hacia arriba o hacia abajo respecto de un paciente promedio.
            Esto hace la estimación auditable caso por caso.
          </p>
        </Section>

        <Section title="8. Limitaciones">
          <ul className="list-disc space-y-1 pl-5">
            <li>
              El modelo de cirugía (AUC ≈ 0.79) es algo más débil que el de PTCA (≈ 0.82): la
              mortalidad quirúrgica depende de factores intraoperatorios no capturables antes del
              acto. Al incorporar el EuroSCORE mejoró respecto de versiones previas (≈ 0.72).
            </li>
            <li>
              El EuroSCORE solo se registra desde 2021, por lo que el modelo de cirugía se entrena
              con la era reciente (~1.500 casos). El EuroSCORE es opcional: si no se ingresa, el
              modelo predice igual con el resto de las variables, pero con menor precisión.
            </li>
            <li>
              Las <strong>complicaciones</strong> son más difíciles de anticipar solo con datos
              pre-operatorios (AUC ≈ 0.71): dependen en parte de eventos del propio acto quirúrgico.
              El modelo detecta señal real (mejor que el azar) pero con menor precisión que los de
              mortalidad.
            </li>
            <li>
              La capacidad predictiva está limitada por los <strong>datos disponibles</strong>, no
              por el algoritmo. Sumar variables o modelos más complejos no mejoró los resultados.
            </li>
            <li>
              No considera variables no registradas ni la evolución clínica en tiempo real.
            </li>
            <li>
              Es un modelo <strong>estadístico poblacional</strong>: no debe usarse como criterio
              único para decisiones sobre un paciente individual.
            </li>
          </ul>
        </Section>
      </div>
    </PageShell>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 pt-4 text-sm leading-relaxed text-foreground">
        {children}
      </CardContent>
    </Card>
  )
}

function RocChart({ title, auc, curve }: { title: string; auc: number; curve: RocCurve }) {
  const size = 200
  const pad = 28
  const span = size - pad * 2
  const x = (v: number) => pad + v * span
  const y = (v: number) => size - pad - v * span

  const pts = curve.fpr.map((f, i) => `${x(f)},${y(curve.tpr[i])}`).join(" ")
  const area = `${x(0)},${y(0)} ${pts} ${x(1)},${y(0)}`
  const primary = "var(--color-incc-primary)"

  return (
    <figure className="space-y-1">
      <svg width={size} height={size} className="rounded-lg border bg-background">
        {/* Ejes */}
        <line x1={pad} y1={size - pad} x2={size - pad} y2={size - pad} stroke="currentColor" strokeOpacity={0.25} />
        <line x1={pad} y1={pad} x2={pad} y2={size - pad} stroke="currentColor" strokeOpacity={0.25} />
        {/* Diagonal de azar */}
        <line
          x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)}
          stroke="currentColor" strokeOpacity={0.35} strokeDasharray="4 3"
        />
        {/* Área + curva */}
        <polygon points={area} fill={primary} fillOpacity={0.12} />
        <polyline points={pts} fill="none" stroke={primary} strokeWidth={2} />
        {/* Etiquetas de ejes */}
        <text x={size / 2} y={size - 6} textAnchor="middle" className="fill-muted-foreground" fontSize={9}>
          Falsas alarmas
        </text>
        <text x={10} y={size / 2} textAnchor="middle" transform={`rotate(-90 10 ${size / 2})`} className="fill-muted-foreground" fontSize={9}>
          Detección
        </text>
        <text x={size - pad} y={pad - 8} textAnchor="end" className="fill-foreground" fontSize={11} fontWeight={600}>
          AUC {auc.toFixed(3)}
        </text>
      </svg>
      <figcaption className="text-center text-xs text-muted-foreground">{title}</figcaption>
    </figure>
  )
}

function VariablesBlock({ model }: { model: ModelInfo }) {
  const order: string[] = []
  const byGroup: Record<string, string[]> = {}
  for (const f of model.features) {
    if (!byGroup[f.group]) {
      byGroup[f.group] = []
      order.push(f.group)
    }
    byGroup[f.group].push(f.label)
  }
  return (
    <div className="rounded-lg border p-3">
      <p className="mb-2 text-sm font-medium">{model.title}</p>
      <div className="space-y-2">
        {order.map((g) => (
          <div key={g}>
            <p className="text-xs font-medium text-muted-foreground">{g}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {byGroup[g].map((label) => (
                <span
                  key={label}
                  className="rounded-md bg-muted px-2 py-0.5 text-xs text-foreground"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Traduce el nombre técnico de una feature (ej. "cat__clase_cirugia_4") a una
 *  etiqueta legible usando los campos del modelo. */
function readableFactor(model: ModelInfo, feat: string): string {
  const byKey: Record<string, (typeof model.features)[number]> = {}
  for (const f of model.features) byKey[f.key] = f

  if (feat.startsWith("num__") || feat.startsWith("bin__")) {
    const key = feat.slice(5)
    return byKey[key]?.label ?? key
  }
  if (feat.startsWith("cat__")) {
    const rest = feat.slice(5)
    const selects = model.features
      .filter((f) => f.kind === "select")
      .sort((a, b) => b.key.length - a.key.length)
    for (const f of selects) {
      if (rest.startsWith(`${f.key}_`)) {
        const val = rest.slice(f.key.length + 1)
        const opt = f.options?.find((o) => o.value === val)
        return `${f.label}: ${opt?.label ?? val}`
      }
    }
    return rest
  }
  return feat
}

function FactorsBlock({ model }: { model: ModelInfo }) {
  const ors = model.odds_ratios ?? []
  if (ors.length === 0) return null

  const mapped = ors.map((o) => ({
    label: readableFactor(model, o.feature),
    or: o.odds_ratio,
  }))
  const up = mapped
    .filter((x) => x.or > 1)
    .sort((a, b) => b.or - a.or)
    .slice(0, 5)
  const down = mapped
    .filter((x) => x.or > 0 && x.or < 1)
    .sort((a, b) => a.or - b.or)
    .slice(0, 5)

  return (
    <div className="rounded-lg border p-3">
      <p className="mb-2 text-sm font-medium">{model.title}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-red-600">
            <ArrowUp className="size-3.5" /> Aumentan el riesgo
          </p>
          <ul className="space-y-1">
            {up.map((x) => (
              <li key={x.label} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-foreground">{x.label}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  ×{x.or.toFixed(1)}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-emerald-600">
            <ArrowDown className="size-3.5" /> Reducen el riesgo
          </p>
          <ul className="space-y-1">
            {down.map((x) => (
              <li key={x.label} className="flex items-center justify-between gap-2 text-xs">
                <span className="truncate text-foreground">{x.label}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  ×{x.or.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground">
        ×N = veces que se multiplican las probabilidades (odds) frente a un caso de referencia. En
        variables numéricas, por cada incremento equivalente a su desvío estándar.
      </p>
    </div>
  )
}
