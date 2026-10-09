import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Input } from "./input"
import { Label } from "./label"

describe("Label", () => {
  it("asocia el texto con el input", () => {
    render(
      <>
        <Label htmlFor="anio">Anio</Label>
        <Input id="anio" />
      </>
    )

    expect(screen.getByLabelText("Anio")).toBeInTheDocument()
  })
})
