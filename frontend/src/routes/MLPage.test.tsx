import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import * as predictionsApi from "@/features/predictions/predictionsApi"
import {
  mockModelPtca,
  mockModelSurgery,
  mockModelUnavailable,
  mockPrediction,
} from "@/test/fixtures"
import { MLPage } from "./MLPage"

function renderPage() {
  return render(
    <MemoryRouter>
      <MLPage />
    </MemoryRouter>
  )
}

describe("MLPage", () => {
  afterEach(() => vi.restoreAllMocks())

  it("carga modelos, calcula prediccion y muestra resultado", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([
      mockModelPtca,
      mockModelSurgery,
      mockModelUnavailable,
    ])
    vi.spyOn(predictionsApi, "predict").mockResolvedValue(mockPrediction)

    const ue = userEvent.setup()
    renderPage()

    expect(
      await screen.findByRole("button", { name: /PTCA \/ angioplastia/ })
    ).toBeInTheDocument()

    await ue.type(screen.getByLabelText(/Edad/), "70")
    await ue.click(screen.getByLabelText("Diabetes"))
    await ue.selectOptions(screen.getByLabelText("Clase NYHA"), "2")

    await ue.click(screen.getByRole("button", { name: /Calcular riesgo/ }))

    expect(await screen.findByText("Riesgo alto")).toBeInTheDocument()
    expect(screen.getByText(/12\.0%/)).toBeInTheDocument()
    expect(screen.getByText("¿Qué pesó en esta estimación?")).toBeInTheDocument()
    expect(screen.getByText("Muy buena")).toBeInTheDocument()

    await ue.click(screen.getByText("Ver detalle técnico"))
    expect(screen.getByText("AUC-ROC (validación)")).toBeInTheDocument()

    await ue.click(screen.getByText("¿Cómo leer esta estimación?"))
    expect(screen.getByText(/chance estimada/)).toBeInTheDocument()
  })

  it("cambia de cohort y muestra reliability buena/aceptable", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([
      mockModelPtca,
      { ...mockModelSurgery, metrics: { ...mockModelSurgery.metrics!, auc_roc: 0.72 } },
    ])
    const ue = userEvent.setup()
    renderPage()

    await screen.findByRole("button", { name: /PTCA \/ angioplastia/ })
    await ue.click(screen.getByRole("button", { name: /Cirugia cardiaca/ }))
    expect(await screen.findByText("Aceptable")).toBeInTheDocument()
  })

  it("muestra error al fallar carga de modelos", async () => {
    vi.spyOn(predictionsApi, "listModels").mockRejectedValue(
      new ApiError(500, "API models down")
    )
    renderPage()
    expect(await screen.findByText("API models down")).toBeInTheDocument()
  })

  it("muestra error de prediccion", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([mockModelPtca])
    vi.spyOn(predictionsApi, "predict").mockRejectedValue(new ApiError(400, "bad input"))

    const ue = userEvent.setup()
    renderPage()
    const calc = await screen.findByRole("button", { name: /Calcular riesgo/ })
    await ue.click(calc)
    await waitFor(() => {
      expect(screen.getByText("bad input")).toBeInTheDocument()
    })
  })

  it("lista vacia sin error", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([])
    renderPage()
    expect(await screen.findByText("No hay modelos disponibles.")).toBeInTheDocument()
  })

  it("cubre niveles de riesgo moderado y bajo", async () => {
    vi.spyOn(predictionsApi, "listModels").mockResolvedValue([
      { ...mockModelPtca, metrics: { ...mockModelPtca.metrics!, auc_roc: 0.68 } },
    ])
    vi.spyOn(predictionsApi, "predict")
      .mockResolvedValueOnce({
        ...mockPrediction,
        risk_level: "moderado",
        risk_ratio: null,
        explanation: [],
      })
      .mockResolvedValueOnce({
        ...mockPrediction,
        risk_level: "bajo",
        probability_pct: 1,
      })

    const ue = userEvent.setup()
    renderPage()
    const calc = await screen.findByRole("button", { name: /Calcular riesgo/ })
    expect(screen.getByText("Limitada")).toBeInTheDocument()

    await ue.click(calc)
    expect(await screen.findByText("Riesgo moderado")).toBeInTheDocument()

    await ue.click(screen.getByRole("button", { name: /Calcular riesgo/ }))
    expect(await screen.findByText("Riesgo bajo")).toBeInTheDocument()
  })
})

