import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { HomePage } from "./HomePage"

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => ({
    status: "authenticated",
    user: {
      id: 1,
      username: "dcaraballo",
      full_name: "Diego Caraballo",
      role: "clinico",
      permissions: [],
    },
    token: "t",
    login: vi.fn(),
    logout: vi.fn(),
  }),
}))

describe("HomePage", () => {
  it("saluda al usuario y lista herramientas", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    expect(screen.getByText(/Bienvenido, Diego/)).toBeInTheDocument()
    expect(screen.getByText("KPIs")).toBeInTheDocument()
    expect(screen.getByText("Predicciones ML")).toBeInTheDocument()
    expect(screen.getByText("Asistente IA")).toBeInTheDocument()
  })
})
