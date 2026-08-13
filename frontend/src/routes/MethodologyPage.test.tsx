import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import * as predictionsApi from "@/features/predictions/predictionsApi"
import { mockModelPtca, mockModelSurgery } from "@/test/fixtures"
import { MethodologyPage } from "./MethodologyPage"

describe("MethodologyPage", () => {
  afterEach(() => vi.restoreAllMocks())

  it("renderiza metodologia con metricas, ROC y factores", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([
      mockModelPtca,
      mockModelSurgery,
    ])

    render(
      <MemoryRouter>
        <MethodologyPage />
      </MemoryRouter>
    )

    expect(await screen.findByText("Metodología de los modelos")).toBeInTheDocument()
    expect(screen.getByText("Curvas ROC")).toBeInTheDocument()
    expect(screen.getAllByText("Aumentan el riesgo").length).toBeGreaterThan(0)
    expect(screen.getByText("Clase NYHA: II")).toBeInTheDocument()
    expect(screen.getAllByText("Diabetes").length).toBeGreaterThan(0)
  })


  it("muestra error de carga", async () => {
    vi.spyOn(predictionsApi, "listModels").mockRejectedValue(
      new ApiError(500, "metrics fail")
    )
    render(
      <MemoryRouter>
        <MethodologyPage />
      </MemoryRouter>
    )
    expect(await screen.findAllByText("metrics fail")).toHaveLength(2)
  })
})
