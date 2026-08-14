import { describe, expect, it } from "vitest"

import {
  getNavItem,
  getNavItemsForRole,
  NAV_ITEMS,
  roleCanAccessPath,
} from "./navigation"

describe("navigation", () => {
  it("expone rutas principales disponibles", () => {
    expect(NAV_ITEMS.length).toBeGreaterThanOrEqual(4)
    expect(NAV_ITEMS.every((item) => item.available)).toBe(true)
  })

  it("resuelve items por path", () => {
    expect(getNavItem("/dashboard")?.label).toBe("Inicio")
    expect(getNavItem("/ml")?.short).toBe("ML")
    expect(getNavItem("/nope")).toBeUndefined()
  })

  it("filtra ML segun rol", () => {
    const clinicoPaths = getNavItemsForRole("clinico").map((i) => i.path)
    const gestionPaths = getNavItemsForRole("gestion").map((i) => i.path)
    expect(clinicoPaths).toContain("/ml")
    expect(gestionPaths).not.toContain("/ml")
    expect(gestionPaths).toContain("/kpis")
    expect(roleCanAccessPath("/ml/metodologia", "admin")).toBe(true)
    expect(roleCanAccessPath("/ml", "gestion")).toBe(false)
  })
})
