import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import * as metabaseApi from "@/features/metabase/metabaseApi"
import { KpisPage } from "./KpisPage"

describe("KpisPage", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it("lista categorias y embebe dashboard", async () => {
    vi.spyOn(metabaseApi, "getMetabaseEmbedUrl").mockResolvedValue({
      iframe_url: "http://metabase.test/embed/1",
      dashboard_id: 10,
      expires_in: 600,
    })

    const ue = userEvent.setup()
    render(<KpisPage />)

    expect(screen.getByText("KPIs")).toBeInTheDocument()
    await ue.click(screen.getByRole("button", { name: /Actos · Volumen/ }))

    expect(await screen.findByTitle("Indicador Actos · Volumen y origen")).toBeInTheDocument()
    fireEvent.load(screen.getByTitle("Indicador Actos · Volumen y origen"))

    await waitFor(() => {
      expect(screen.queryByText("Cargando indicador…")).not.toBeInTheDocument()
    })

    await ue.click(screen.getByRole("button", { name: /Volver/ }))
    expect(screen.getByText("Indicadores clave del INCC segmentados por categoría.")).toBeInTheDocument()
  })

  it("muestra error y permite reintentar", async () => {
    const spy = vi
      .spyOn(metabaseApi, "getMetabaseEmbedUrl")
      .mockRejectedValueOnce(new ApiError(503, "Metabase caido"))
      .mockResolvedValueOnce({
        iframe_url: "http://metabase.test/embed/ok",
        dashboard_id: 10,
        expires_in: 600,
      })

    const ue = userEvent.setup()
    render(<KpisPage />)
    await ue.click(screen.getByRole("button", { name: /Actos · Volumen/ }))

    expect(await screen.findByText("Metabase caido")).toBeInTheDocument()
    await ue.click(screen.getByRole("button", { name: /Reintentar/ }))
    expect(await screen.findByTitle("Indicador Actos · Volumen y origen")).toBeInTheDocument()
    expect(spy).toHaveBeenCalledTimes(2)
  })
})
