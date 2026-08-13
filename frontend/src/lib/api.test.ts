import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  ApiError,
  apiRequest,
  getStoredToken,
  registerUnauthorizedHandler,
  setStoredToken,
} from "./api"

describe("token storage", () => {
  it("guarda y limpia el token", () => {
    setStoredToken("abc")
    expect(getStoredToken()).toBe("abc")
    setStoredToken(null)
    expect(getStoredToken()).toBeNull()
  })

  it("tolera fallos de localStorage", () => {
    const getSpy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    const setSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked")
    })
    expect(getStoredToken()).toBeNull()
    expect(() => setStoredToken("x")).not.toThrow()
    getSpy.mockRestore()
    setSpy.mockRestore()
  })
})

describe("apiRequest", () => {
  beforeEach(() => {
    setStoredToken("tok-1")
    registerUnauthorizedHandler(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    registerUnauthorizedHandler(null)
  })

  it("hace GET autenticado y parsea JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    )
    vi.stubGlobal("fetch", fetchMock)

    const data = await apiRequest<{ ok: boolean }>("/health")
    expect(data).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledOnce()
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe("Bearer tok-1")
  })

  it("envía body JSON y puede desactivar auth", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: "t" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    )
    vi.stubGlobal("fetch", fetchMock)

    await apiRequest("/auth/login", {
      method: "POST",
      body: { username: "a", password: "b" },
      auth: false,
    })
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBeUndefined()
    expect(init.headers["Content-Type"]).toBe("application/json")
    expect(JSON.parse(init.body)).toEqual({ username: "a", password: "b" })
  })

  it("lanza ApiError en respuestas no OK", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Credenciales inválidas" }), {
          status: 401,
          statusText: "Unauthorized",
          headers: { "content-type": "application/json" },
        })
      )
    )

    const handler = vi.fn()
    registerUnauthorizedHandler(handler)

    await expect(apiRequest("/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      message: "Credenciales inválidas",
    })
    expect(handler).toHaveBeenCalledOnce()
  })

  it("usa mensaje genérico si no hay detail string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: { field: "x" } }), {
          status: 422,
          statusText: "Unprocessable Entity",
          headers: { "content-type": "application/json" },
        })
      )
    )

    await expect(apiRequest("/x")).rejects.toBeInstanceOf(ApiError)
    await expect(apiRequest("/x")).rejects.toMatchObject({ status: 422 })
  })

  it("lanza ApiError de red si fetch falla", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")))
    await expect(apiRequest("/x")).rejects.toMatchObject({
      status: 0,
      message: "No se pudo conectar con el servidor",
    })
  })
})
