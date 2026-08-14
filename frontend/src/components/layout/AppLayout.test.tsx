import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import { AppLayout } from "./AppLayout"

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

describe("AppLayout", () => {
  it("renderiza outlet y cierra menu al cambiar de ruta", async () => {
    const ue = userEvent.setup()
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<div>home-outlet</div>} />
            <Route path="/kpis" element={<div>kpis-outlet</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByText("home-outlet")).toBeInTheDocument()
    await ue.click(screen.getByLabelText("Abrir menu"))
    await ue.click(screen.getByRole("link", { name: "KPIs" }))
    expect(await screen.findByText("kpis-outlet")).toBeInTheDocument()
  })
})
