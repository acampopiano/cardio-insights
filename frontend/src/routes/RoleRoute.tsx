import type { ReactNode } from "react"
import { Navigate } from "react-router-dom"

import { useAuth } from "@/features/auth/useAuth"
import { normalizeRole } from "@/lib/navigation"

interface RoleRouteProps {
  children: ReactNode
  roles: readonly string[]
  fallbackTo?: string
}

/** Requiere autenticación previa (usar dentro de ProtectedRoute) y uno de los roles. */
export function RoleRoute({
  children,
  roles,
  fallbackTo = "/dashboard",
}: RoleRouteProps) {
  const { user } = useAuth()
  const role = normalizeRole(user?.role)
  const allowed = roles.some((r) => r.toLowerCase() === role)

  if (!allowed) {
    return <Navigate to={fallbackTo} replace />
  }

  return <>{children}</>
}
