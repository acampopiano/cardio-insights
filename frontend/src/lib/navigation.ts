import {
  BarChart3,
  Brain,
  Home,
  MessageSquare,
  TrendingUp,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

export interface NavItem {
  path: string
  label: string
  short: string
  icon: LucideIcon
  description: string
  available: boolean
  comingSoonHint?: string
  features?: string[]
}

export const NAV_ITEMS: NavItem[] = [
  {
    path: "/dashboard",
    label: "Inicio",
    short: "Inicio",
    icon: Home,
    description: "Vista general de las herramientas disponibles en la plataforma.",
    available: true,
  },
  {
    path: "/reportes",
    label: "Reportes",
    short: "Reportes",
    icon: BarChart3,
    description:
      "Dashboards interactivos de Metabase con datos clinicos del INCC.",
    available: false,
    comingSoonHint:
      "Integraremos los reportes embebidos de Metabase usando los tokens de embedding del backend.",
    features: [
      "Mortalidad operatoria",
      "Volumen quirurgico mensual",
      "Tiempos de espera por procedimiento",
      "Indicadores de hemodinamia",
    ],
  },
  {
    path: "/kpis",
    label: "KPIs",
    short: "KPIs",
    icon: TrendingUp,
    description:
      "Indicadores clave de la actividad clinica con filtros por periodo y tipo de acto medico.",
    available: false,
    comingSoonHint:
      "Conectaremos /api/v1/kpis/query y /api/v1/dashboard/summary para mostrar las metricas en cards interactivas.",
    features: [
      "Mortalidad 30 dias",
      "Volumen de cirugia cardiaca",
      "Volumen de PTCA",
      "Tiempo promedio en UCI",
    ],
  },
  {
    path: "/ml",
    label: "Predicciones ML",
    short: "ML",
    icon: Brain,
    description:
      "Modelos predictivos entrenados sobre datos historicos del INCC.",
    available: false,
    comingSoonHint:
      "Vamos a exponer un endpoint para correr predicciones sobre pacientes concretos. El frontend cargara los inputs y mostrara el score con explicabilidad.",
    features: [
      "Riesgo de mortalidad perioperatoria",
      "Probabilidad de complicaciones",
      "Riesgo de reingreso a 30 dias",
    ],
  },
  {
    path: "/agente",
    label: "Asistente IA",
    short: "Asistente",
    icon: MessageSquare,
    description:
      "Consultas en lenguaje natural sobre los datos del INCC, respaldadas por un LLM con acceso a las vistas SQL.",
    available: false,
    comingSoonHint:
      "El agente respondera preguntas como 'cuantas cirugias hubo el mes pasado' o 'mostrame la evolucion de la mortalidad a 30 dias'.",
    features: [
      "Consultas conversacionales",
      "Generacion de graficos on demand",
      "Citas a la fuente de los datos",
    ],
  },
]

export function getNavItem(path: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => item.path === path)
}
