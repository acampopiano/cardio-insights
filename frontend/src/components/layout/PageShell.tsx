import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

interface PageShellProps {
  children: ReactNode
  className?: string
}

/**
 * Contenedor de contenido alineado al layout de Predicciones ML:
 * max-w-6xl, px-4/sm:px-6, py-6 — mismo aire respecto a sidebar y header.
 */
export function PageShell({ children, className }: PageShellProps) {
  return (
    <div className={cn("mx-auto w-full max-w-6xl px-4 py-6 sm:px-6", className)}>
      {children}
    </div>
  )
}
