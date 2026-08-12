import { useCallback, useEffect, useRef, useState } from "react"
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  HeartPulse,
  Loader2,
  RefreshCw,
  Stethoscope,
  TrendingUp,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import { PageShell } from "@/components/layout/PageShell"
import { Button } from "@/components/ui/button"
import { ApiError } from "@/lib/api"
import { getMetabaseEmbedUrl } from "@/features/metabase/metabaseApi"

interface KpiCategory {
  dashboardId: number
  label: string
  description: string
  icon: LucideIcon
}

// Categorías planas: cada una es un dashboard independiente (sin tabs) en Metabase.
const CATEGORIES: KpiCategory[] = [
  {
    dashboardId: 10,
    label: "Actos · Volumen y origen",
    description:
      "Totales, facturación/origen, mapa y envíos por centro o médico.",
    icon: Activity,
  },
  {
    dashboardId: 11,
    label: "Actos · Por procedimiento",
    description:
      "Series de cateterismos, cirugías, TAVI, marcapasos y ecografías.",
    icon: Activity,
  },
  {
    dashboardId: 12,
    label: "Cirugía · Indicadores",
    description: "Volumen, Euroscore, tiempos de espera y evolución anual.",
    icon: Stethoscope,
  },
  {
    dashboardId: 13,
    label: "Cirugía · Pacientes y reintervenciones",
    description: "Mapa de pacientes, reintervenciones, IOT y estadías.",
    icon: Stethoscope,
  },
  {
    dashboardId: 14,
    label: "Cirugía · Perfil clínico",
    description: "Edad, tops clínicos y ecografías asociadas.",
    icon: Stethoscope,
  },
  {
    dashboardId: 15,
    label: "Hemodinamia · Resumen",
    description:
      "Totales, mapa de pacientes y stents (año seleccionado y acumulado).",
    icon: HeartPulse,
  },
  {
    dashboardId: 16,
    label: "Hemodinamia · Evolución",
    description: "Series anuales de CAT/PTCA, TAVI, marcapasos y desfibrilador.",
    icon: HeartPulse,
  },
  {
    dashboardId: 8,
    label: "Factores de Riesgo - Complicaciones",
    description: "Riesgo perioperatorio y complicaciones asociadas.",
    icon: AlertTriangle,
  },
  {
    dashboardId: 17,
    label: "Mortalidad",
    description:
      "Mortalidad a 30 días post-cirugía y PTCA, y causas de fallecimiento.",
    icon: AlertCircle,
  },
]

export function KpisPage() {
  const [selected, setSelected] = useState<KpiCategory | null>(null)

  if (selected) {
    return (
      <EmbeddedCategory category={selected} onBack={() => setSelected(null)} />
    )
  }

  return (
    <PageShell>
      <header className="mb-6 flex items-center gap-3">
        <div
          className="grid size-11 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]"
          aria-hidden="true"
        >
          <TrendingUp className="size-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">KPIs</h1>
          <p className="text-sm text-muted-foreground">
            Indicadores clave del INCC segmentados por categoría.
          </p>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon
          return (
            <button
              key={cat.dashboardId}
              type="button"
              onClick={() => setSelected(cat)}
              className="group flex items-start gap-4 rounded-xl border bg-card p-5 text-left transition-colors hover:border-[var(--color-incc-primary)]/40 hover:bg-muted/40"
            >
              <div className="grid size-12 shrink-0 place-items-center rounded-xl bg-[var(--color-incc-primary)]/10 text-[var(--color-incc-primary)]">
                <Icon className="size-6" />
              </div>
              <div className="space-y-1">
                <h2 className="font-semibold leading-tight">{cat.label}</h2>
                <p className="text-sm text-muted-foreground">{cat.description}</p>
              </div>
            </button>
          )
        })}
      </div>
    </PageShell>
  )
}

interface EmbeddedCategoryProps {
  category: KpiCategory
  onBack: () => void
}

function EmbeddedCategory({ category, onBack }: EmbeddedCategoryProps) {
  const [iframeUrl, setIframeUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [frameLoaded, setFrameLoaded] = useState(false)
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadEmbed = useCallback(async () => {
    setLoading(true)
    setError(null)
    setFrameLoaded(false)
    try {
      const res = await getMetabaseEmbedUrl(category.dashboardId)
      setIframeUrl(res.iframe_url)
      if (refreshTimer.current) clearTimeout(refreshTimer.current)
      // Renovamos el token poco antes de que expire para no cortar la sesión.
      const refreshInMs = Math.max((res.expires_in - 60) * 1000, 60_000)
      refreshTimer.current = setTimeout(() => {
        void loadEmbed()
      }, refreshInMs)
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "No se pudo cargar el indicador de Metabase."
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [category.dashboardId])

  useEffect(() => {
    void loadEmbed()
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current)
    }
  }, [loadEmbed])

  // Casi fullscreen: solo el header de la app (~3.5rem). El main no scrollea;
  // el único scroll queda dentro del iframe de Metabase.
  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full flex-col overflow-hidden">
      <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b bg-background px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={onBack}
            className="-ml-1 text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Volver
          </Button>
          <div className="h-5 w-px shrink-0 bg-border" aria-hidden="true" />
          <h1 className="truncate text-sm font-semibold sm:text-base">
            {category.label}
          </h1>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void loadEmbed()}
          disabled={loading}
        >
          <RefreshCw className={loading ? "size-4 animate-spin" : "size-4"} />
          Actualizar
        </Button>
      </header>

      <div className="relative min-h-0 flex-1 bg-muted/20">
        {error && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 p-6 text-center">
            <div className="grid size-14 place-items-center rounded-2xl bg-destructive/10 text-destructive">
              <AlertCircle className="size-7" />
            </div>
            <div className="space-y-1">
              <p className="font-medium">No se pudo cargar el indicador</p>
              <p className="max-w-md text-sm text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => void loadEmbed()}>
              <RefreshCw className="size-4" />
              Reintentar
            </Button>
          </div>
        )}

        {!error && (loading || !frameLoaded || !iframeUrl) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-muted/20 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Cargando indicador…
          </div>
        )}

        {!error && iframeUrl && (
          <iframe
            key={iframeUrl}
            src={iframeUrl}
            title={`Indicador ${category.label}`}
            className="size-full border-0"
            onLoad={() => setFrameLoaded(true)}
          />
        )}
      </div>
    </div>
  )
}
