import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { ProtectedRoute } from "./ProtectedRoute"

const useAuthMock = vi.fn()

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => useAuthMock(),
}))

function renderAt(status: "loading" | "authenticated" | "unauthenticated") {
  useAuthMock.mockReturnValue({
    status,
    user: null,
    token: null,
    login: vi.fn(),
    logout: vi.fn(),
  })

  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <Routes>
        <Route path="/" element={<div>login</div>} />
        <Route
          path="/secret"
          element={
            <ProtectedRoute>
              <div>protected</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe("ProtectedRoute", () => {
  it("muestra spinner mientras carga", () => {
    renderAt("loading")
    expect(screen.getByText("Verificando sesion...")).toBeInTheDocument()
  })

  it("redirige a login si no hay sesion", () => {
    renderAt("unauthenticated")
    expect(screen.getByText("login")).toBeInTheDocument()
    expect(screen.queryByText("protected")).not.toBeInTheDocument()
  })

  it("renderiza children autenticado", () => {
    renderAt("authenticated")
    expect(screen.getByText("protected")).toBeInTheDocument()
  })
})
