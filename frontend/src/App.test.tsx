import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import App from "./App"
import * as authApi from "@/features/auth/authApi"

vi.mock("@/features/predictions/predictionsApi", () => ({
  listModels: vi.fn().mockResolvedValue([]),
  predict: vi.fn(),
}))

vi.mock("@/features/metabase/metabaseApi", () => ({
  getMetabaseEmbedUrl: vi.fn().mockResolvedValue({
    iframe_url: "http://x",
    dashboard_id: 1,
    expires_in: 600,
  }),
}))

vi.mock("@/features/chat/chatApi", () => ({
  askChat: vi.fn(),
}))

describe("App", () => {
  it("muestra login por defecto", async () => {
    vi.spyOn(authApi, "me").mockRejectedValue(new Error("no session"))
    render(<App />)
    expect(await screen.findByText("Iniciar sesion")).toBeInTheDocument()
  })

  it("redirige rutas desconocidas al login", async () => {
    vi.spyOn(authApi, "me").mockRejectedValue(new Error("no session"))
    window.history.pushState({}, "", "/ruta-inexistente")
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText("Iniciar sesion")).toBeInTheDocument()
    })
  })
})
