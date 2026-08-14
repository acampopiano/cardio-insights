import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { Header } from "./Header"

const logout = vi.fn()
const useAuthMock = vi.fn()

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => useAuthMock(),
}))

describe("Header", () => {
  it("abre menu de usuario y cierra sesion", async () => {
    useAuthMock.mockReturnValue({
      status: "authenticated",
      user: {
        id: 1,
        username: "dcaraballo",
        full_name: "Diego Caraballo",
        role: "clinico",
        permissions: ["kpis:read"],
      },
      token: "t",
      login: vi.fn(),
      logout,
    })

    const onMenu = vi.fn()
    const ue = userEvent.setup()
    render(
      <MemoryRouter>
        <Header onMenuClick={onMenu} />
      </MemoryRouter>
    )

    await ue.click(screen.getByLabelText("Abrir menu"))
    expect(onMenu).toHaveBeenCalled()

    await ue.click(screen.getByLabelText("Menu de Diego Caraballo"))
    expect(screen.queryByText("Permisos")).not.toBeInTheDocument()
    expect(screen.queryByText("Mi perfil")).not.toBeInTheDocument()
    expect(screen.queryByText("Preferencias")).not.toBeInTheDocument()
    expect(screen.getByText("Clinico")).toBeInTheDocument()

    await ue.click(screen.getByText("Cerrar sesion"))
    expect(logout).toHaveBeenCalled()
  })

  it("muestra badge de admin", async () => {
    useAuthMock.mockReturnValue({
      status: "authenticated",
      user: {
        id: 2,
        username: "admin",
        full_name: "Admin User",
        role: "admin",
        permissions: [],
      },
      token: "t",
      login: vi.fn(),
      logout: vi.fn(),
    })

    const ue = userEvent.setup()
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>
    )

    await ue.click(screen.getByLabelText("Menu de Admin User"))
    expect(screen.getAllByText("Admin").length).toBeGreaterThan(0)
    expect(screen.getByText("Cerrar sesion")).toBeInTheDocument()
  })
})
