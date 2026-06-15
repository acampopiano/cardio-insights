import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Devuelve hasta 2 iniciales a partir de un nombre completo.
 * Filtra titulos comunes (Dr., Dra., Lic., etc.) antes de calcular.
 */
export function getInitials(fullName: string | null | undefined): string {
  if (!fullName) return "??"
  const parts = fullName
    .trim()
    .split(/\s+/)
    .filter((p) => p.length > 0 && !p.endsWith("."))

  if (parts.length === 0) return "??"
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase()
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}
