import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { ApiError } from "@/lib/api"
import * as chatApi from "@/features/chat/chatApi"
import { AgentePage } from "./AgentePage"

describe("AgentePage", () => {
  it("envia pregunta, muestra SQL y tabla", async () => {
    vi.spyOn(chatApi, "askChat").mockResolvedValue({
      question: "q",
      answer: "Hubo 10 cirugias",
      resolved: true,
      sql: "SELECT 10",
      rows: [
        { anio: 2024, n: 10 },
        { anio: 2025, n: 12 },
      ],
      row_count: 2,
      error: null,
    })

    const ue = userEvent.setup()
    render(<AgentePage />)

    expect(screen.getByText("Preguntale a tus datos")).toBeInTheDocument()

    await ue.type(screen.getByPlaceholderText("Escribí tu pregunta…"), "cuantas?")
    await ue.click(screen.getByRole("button", { name: "Enviar" }))

    expect(await screen.findByText("Hubo 10 cirugias")).toBeInTheDocument()
    expect(screen.getByText("Ver consulta SQL")).toBeInTheDocument()
    expect(screen.getByText(/Ver datos/)).toBeInTheDocument()
  })

  it("usa sugerencia y maneja error de API", async () => {
    vi.spyOn(chatApi, "askChat").mockRejectedValue(new ApiError(500, "fallo chat"))
    const ue = userEvent.setup()
    render(<AgentePage />)

    await ue.click(
      screen.getByRole("button", {
        name: "¿Cuántas cirugías se realizaron en 2024?",
      })
    )

    expect(await screen.findByText("fallo chat")).toBeInTheDocument()
    expect(screen.getByText("No se pudo resolver")).toBeInTheDocument()
  })

  it("muestra preview truncado de muchas filas", async () => {
    const rows = Array.from({ length: 25 }, (_, i) => ({ id: i, v: null }))
    vi.spyOn(chatApi, "askChat").mockResolvedValue({
      question: "q",
      answer: "ok",
      resolved: true,
      sql: null,
      rows,
      row_count: 25,
      error: null,
    })

    const ue = userEvent.setup()
    render(<AgentePage />)
    await ue.type(screen.getByPlaceholderText("Escribí tu pregunta…"), "lista")
    await ue.click(screen.getByRole("button", { name: "Enviar" }))

    await waitFor(() => {
      expect(screen.getByText(/Mostrando 20 de 25 filas/)).toBeInTheDocument()
    })
  })
})
