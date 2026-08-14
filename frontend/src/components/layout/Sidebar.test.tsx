import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { Sidebar } from "./Sidebar"

const useAuthMock = vi.fn()

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => useAuthMock(),
}))

function mockRole(role: string) {
  useAuthMock.mockReturnValue({
    status: "authenticated",
    user: {
      id: 1,
      username: "u",
      full_name: "User",
      role,
      permissions: [],
    },
    token: "t",
    login: vi.fn(),
    logout: vi.fn(),
  })
}

describe("Sidebar", () => {
  it("navega, colapsa y cierra mobile", async () => {
    mockRole("clinico")
    const onToggle = vi.fn()
    const onClose = vi.fn()
    const ue = userEvent.setup()

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Sidebar
          collapsed={false}
          onToggleCollapse={onToggle}
          mobileOpen
          onCloseMobile={onClose}
        />
      </MemoryRouter>
    )

    expect(screen.getByLabelText("Navegacion principal")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Inicio" })).toHaveAttribute(
      "aria-current",
      "page"
    )
    expect(screen.getByRole("link", { name: /Predicciones ML/i })).toBeInTheDocument()

    await ue.click(screen.getByLabelText("Cerrar menu"))
    expect(onClose).toHaveBeenCalled()

    await ue.click(screen.getByLabelText("Colapsar sidebar"))
    expect(onToggle).toHaveBeenCalled()
  })

  it("oculta ML para rol gestion", () => {
    mockRole("gestion")
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Sidebar
          collapsed={false}
          onToggleCollapse={vi.fn()}
          mobileOpen={false}
          onCloseMobile={vi.fn()}
        />
      </MemoryRouter>
    )
    expect(screen.queryByRole("link", { name: /Predicciones ML/i })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /KPIs/i })).toBeInTheDocument()
  })

  it("muestra boton expandir cuando esta colapsado", () => {
    mockRole("admin")
    render(
      <MemoryRouter>
        <Sidebar
          collapsed
          onToggleCollapse={vi.fn()}
          mobileOpen={false}
          onCloseMobile={vi.fn()}
        />
      </MemoryRouter>
    )
    expect(screen.getByLabelText("Expandir sidebar")).toBeInTheDocument()
  })
})
