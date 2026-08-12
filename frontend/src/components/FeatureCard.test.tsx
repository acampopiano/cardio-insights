import { render, screen } from "@testing-library/react"
import { Home } from "lucide-react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it } from "vitest"

import type { NavItem } from "@/lib/navigation"
import { FeatureCard } from "./FeatureCard"

const base: NavItem = {
  path: "/demo",
  label: "Demo",
  short: "Demo",
  icon: Home,
  description: "Descripcion",
  available: true,
}

describe("FeatureCard", () => {
  it("muestra la herramienta con enlace a abrir", () => {
    render(
      <MemoryRouter>
        <FeatureCard item={base} />
      </MemoryRouter>
    )
    expect(screen.getByText("Demo")).toBeInTheDocument()
    expect(screen.getByText("Descripcion")).toBeInTheDocument()
    expect(screen.getByText("Abrir")).toBeInTheDocument()
    expect(screen.queryByText("Disponible")).not.toBeInTheDocument()
    expect(screen.queryByText("Pronto")).not.toBeInTheDocument()
    expect(screen.getByRole("link")).toHaveAttribute("href", "/demo")
  })
})
