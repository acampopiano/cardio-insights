import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Alert, AlertDescription, AlertTitle } from "./alert"

describe("Alert", () => {
  it("renderiza titulo y descripcion", () => {
    render(
      <Alert>
        <AlertTitle>Error de sesion</AlertTitle>
        <AlertDescription>Revisa tus credenciales.</AlertDescription>
      </Alert>
    )

    expect(screen.getByRole("alert")).toBeInTheDocument()
    expect(screen.getByText("Error de sesion")).toBeInTheDocument()
    expect(screen.getByText("Revisa tus credenciales.")).toBeInTheDocument()
  })

  it("aplica la variante destructive", () => {
    render(
      <Alert variant="destructive" className="extra">
        <AlertTitle>Fallo</AlertTitle>
      </Alert>
    )

    const alert = screen.getByRole("alert")
    expect(alert.className).toMatch(/destructive/)
    expect(alert.className).toMatch(/extra/)
  })
})
