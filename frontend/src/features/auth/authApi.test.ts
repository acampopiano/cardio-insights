import { afterEach, describe, expect, it, vi } from "vitest"

import * as api from "@/lib/api"
import { login, logout, me } from "./authApi"

describe("authApi", () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("login sin auth header", async () => {
    const spy = vi.spyOn(api, "apiRequest").mockResolvedValue({
      access_token: "t",
      token_type: "bearer",
      expires_in: 60,
      user: {
        id: 1,
        username: "dcaraballo",
        full_name: "Diego Caraballo",
        role: "clinico",
        permissions: [],
      },
    })

    await login({ username: "dcaraballo", password: "x" })
    expect(spy).toHaveBeenCalledWith("/auth/login", {
      method: "POST",
      body: { username: "dcaraballo", password: "x" },
      auth: false,
    })
  })

  it("logout y me", async () => {
    const spy = vi.spyOn(api, "apiRequest").mockResolvedValue({})
    await logout()
    await me()
    expect(spy).toHaveBeenCalledWith("/auth/logout", { method: "POST" })
    expect(spy).toHaveBeenCalledWith("/auth/me", { method: "GET" })
  })
})
