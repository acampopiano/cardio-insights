import {
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
  /** Si está definido, solo esos roles ven el item. */
  roles?: string[]
  comingSoonHint?: string
  features?: string[]
}

/** Roles con acceso a predicciones ML (alineado con backend ML_ACCESS_ROLES). */
export const ML_ACCESS_ROLES = ["admin", "clinico"] as const

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
    path: "/kpis",
    label: "KPIs",
    short: "KPIs",
    icon: TrendingUp,
    description:
      "Indicadores clave del INCC en dashboards de Metabase, con filtros y exportacion.",
    available: true,
    features: [
      "Actos (volumen y por procedimiento)",
      "Cirugia (indicadores, pacientes, perfil)",
      "Hemodinamia (resumen y evolucion)",
      "Factores de riesgo y complicaciones",
      "Exportacion de resultados (CSV / Excel / imagen)",
    ],
  },
  {
    path: "/ml",
    label: "Predicciones ML",
    short: "ML",
    icon: Brain,
    description:
      "Modelos predictivos entrenados sobre datos historicos del INCC.",
    available: true,
    roles: [...ML_ACCESS_ROLES],
    features: [
      "Riesgo de mortalidad en PTCA / angioplastia",
      "Riesgo de mortalidad quirurgica a 30 dias",
      "Explicabilidad: factores de mayor peso",
    ],
  },
  {
    path: "/agente",
    label: "Asistente IA",
    short: "Asistente",
    icon: MessageSquare,
    description:
      "Consultas en lenguaje natural sobre los datos del INCC, respaldadas por un LLM con acceso de solo lectura a la base.",
    available: true,
    features: [
      "Consultas conversacionales",
      "SQL generado y auditable",
      "Acceso de solo lectura a los datos",
    ],
  },
]

export function normalizeRole(role: string | null | undefined): string {
  return (role ?? "").trim().toLowerCase()
}

export function roleCanAccessItem(
  item: NavItem,
  role: string | null | undefined
): boolean {
  if (!item.roles || item.roles.length === 0) return true
  const normalized = normalizeRole(role)
  return item.roles.some((allowed) => allowed.toLowerCase() === normalized)
}

export function getNavItemsForRole(role: string | null | undefined): NavItem[] {
  return NAV_ITEMS.filter((item) => roleCanAccessItem(item, role))
}

export function getNavItem(path: string): NavItem | undefined {
  return NAV_ITEMS.find((item) => item.path === path)
}

export function roleCanAccessPath(
  path: string,
  role: string | null | undefined
): boolean {
  const item =
    getNavItem(path) ??
    NAV_ITEMS.find(
      (nav) => path === nav.path || path.startsWith(`${nav.path}/`)
    )
  if (!item) return true
  return roleCanAccessItem(item, role)
}
