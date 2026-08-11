import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { setStoredToken } from "@/lib/api"
import type { UserPublic } from "@/types/auth"
import { AuthProvider } from "./AuthContext"
import { useAuth } from "./useAuth"
import * as authApi from "./authApi"

const user: UserPublic = {
  id: 2,
  username: "dcaraballo",
  full_name: "Diego Caraballo",
  role: "clinico",
  permissions: ["read"],
}

function Probe() {
  const auth = useAuth()
  return (
    <div>
      <span data-testid="status">{auth.status}</span>
      <span data-testid="user">{auth.user?.username ?? "none"}</span>
      <button type="button" onClick={() => auth.login({ username: "a", password: "b" })}>
        login
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        logout
      </button>
    </div>
  )
}

describe("AuthProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    setStoredToken(null)
  })

  it("empieza unauthenticated sin token", () => {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )
    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated")
  })

  it("hidrata sesion con token valido", async () => {
    setStoredToken("tok")
    vi.spyOn(authApi, "me").mockResolvedValue({ user })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated")
    })
    expect(screen.getByTestId("user")).toHaveTextContent("dcaraballo")
  })

  it("limpia sesion si /me falla", async () => {
    setStoredToken("bad")
    vi.spyOn(authApi, "me").mockRejectedValue(new Error("401"))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated")
    })
    expect(localStorage.getItem("cardio_insights.token")).toBeNull()
  })

  it("login guarda token y usuario", async () => {
    vi.spyOn(authApi, "login").mockResolvedValue({
      access_token: "new-tok",
      token_type: "bearer",
      expires_in: 3600,
      user,
    })
    // After login sets token, me() may fire from the token effect
    vi.spyOn(authApi, "me").mockResolvedValue({ user })

    const ue = userEvent.setup()
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await ue.click(screen.getByRole("button", { name: "login" }))
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated")
    })
    expect(localStorage.getItem("cardio_insights.token")).toBe("new-tok")
  })

  it("logout limpia aunque el API falle", async () => {
    setStoredToken("tok")
    vi.spyOn(authApi, "me").mockResolvedValue({ user })
    vi.spyOn(authApi, "logout").mockRejectedValue(new Error("offline"))

    const ue = userEvent.setup()
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("authenticated")
    })

    await ue.click(screen.getByRole("button", { name: "logout" }))
    await waitFor(() => {
      expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated")
    })
  })

  it("useAuth fuera del provider lanza", () => {
    expect(() => render(<Probe />)).toThrow(
      "useAuth debe usarse dentro de <AuthProvider>"
    )
  })
})
