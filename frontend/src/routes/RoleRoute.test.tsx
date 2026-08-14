import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { RoleRoute } from "./RoleRoute"

const useAuthMock = vi.fn()

vi.mock("@/features/auth/useAuth", () => ({
  useAuth: () => useAuthMock(),
}))

function renderWithRole(role: string) {
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

  return render(
    <MemoryRouter initialEntries={["/ml"]}>
      <Routes>
        <Route path="/dashboard" element={<div>dashboard</div>} />
        <Route
          path="/ml"
          element={
            <RoleRoute roles={["admin", "clinico"]}>
              <div>ml-page</div>
            </RoleRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe("RoleRoute", () => {
  it("permite clinico", () => {
    renderWithRole("clinico")
    expect(screen.getByText("ml-page")).toBeInTheDocument()
  })

  it("redirige gestion al dashboard", () => {
    renderWithRole("gestion")
    expect(screen.getByText("dashboard")).toBeInTheDocument()
    expect(screen.queryByText("ml-page")).not.toBeInTheDocument()
  })
})
