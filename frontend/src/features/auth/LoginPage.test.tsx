import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import { LoginPage } from "./LoginPage"

const loginMock = vi.fn()
const useAuthMock = vi.fn()

vi.mock("./useAuth", () => ({
  useAuth: () => useAuthMock(),
}))

function renderLogin(
  status: "loading" | "authenticated" | "unauthenticated" = "unauthenticated"
) {
  useAuthMock.mockReturnValue({
    status,
    user: null,
    token: null,
    login: loginMock,
    logout: vi.fn(),
  })

  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/dashboard" element={<div>dashboard</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe("LoginPage", () => {
  it("redirige si ya esta autenticado", () => {
    renderLogin("authenticated")
    expect(screen.getByText("dashboard")).toBeInTheDocument()
  })

  it("valida campos requeridos", async () => {
    const ue = userEvent.setup()
    renderLogin()
    await ue.click(screen.getByRole("button", { name: "Entrar" }))
    expect(await screen.findByText("Ingresa tu usuario")).toBeInTheDocument()
    expect(screen.getByText("Ingresa tu contrasena")).toBeInTheDocument()
  })

  it("loguea y navega al dashboard", async () => {
    loginMock.mockResolvedValue({
      id: 2,
      username: "dcaraballo",
      full_name: "Diego Caraballo",
      role: "clinico",
      permissions: [],
    })
    const ue = userEvent.setup()
    renderLogin()

    await ue.type(screen.getByLabelText("Usuario"), "dcaraballo")
    await ue.type(screen.getByLabelText("Contrasena"), "Demo1234!")
    await ue.click(screen.getByRole("button", { name: "Entrar" }))

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        username: "dcaraballo",
        password: "Demo1234!",
      })
    })
    expect(await screen.findByText("dashboard")).toBeInTheDocument()
  })

  it("muestra ApiError del servidor", async () => {
    loginMock.mockRejectedValue(new ApiError(401, "Credenciales invalidas"))
    const ue = userEvent.setup()
    renderLogin()

    await ue.type(screen.getByLabelText("Usuario"), "bad")
    await ue.type(screen.getByLabelText("Contrasena"), "bad")
    await ue.click(screen.getByRole("button", { name: "Entrar" }))

    expect(await screen.findByText("Credenciales invalidas")).toBeInTheDocument()
  })

  it("muestra mensaje de red si status es 0", async () => {
    loginMock.mockRejectedValue(new ApiError(0, "offline"))
    const ue = userEvent.setup()
    renderLogin()

    await ue.type(screen.getByLabelText("Usuario"), "a")
    await ue.type(screen.getByLabelText("Contrasena"), "b")
    await ue.click(screen.getByRole("button", { name: "Entrar" }))

    expect(
      await screen.findByText(/No se pudo conectar con el servidor/)
    ).toBeInTheDocument()
  })

  it("alterna visibilidad de contrasena", async () => {
    const ue = userEvent.setup()
    renderLogin()
    const password = screen.getByLabelText("Contrasena")
    expect(password).toHaveAttribute("type", "password")
    await ue.click(screen.getByLabelText("Mostrar contrasena"))
    expect(password).toHaveAttribute("type", "text")
  })
})
