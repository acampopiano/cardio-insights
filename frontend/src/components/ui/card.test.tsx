import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "./card"

describe("Card", () => {
  it("arma las secciones de una tarjeta", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Indicadores</CardTitle>
          <CardDescription>Resumen del periodo</CardDescription>
        </CardHeader>
        <CardContent>12 actos</CardContent>
        <CardFooter>Ver detalle</CardFooter>
      </Card>
    )

    expect(screen.getByText("Indicadores")).toBeInTheDocument()
    expect(screen.getByText("Resumen del periodo")).toBeInTheDocument()
    expect(screen.getByText("12 actos")).toBeInTheDocument()
    expect(screen.getByText("Ver detalle")).toBeInTheDocument()
  })
})
