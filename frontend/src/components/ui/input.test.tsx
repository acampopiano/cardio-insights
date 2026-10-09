import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { Input } from "./input"

describe("Input", () => {
  it("acepta tipeo, tipo y estado invalido", async () => {
    const ue = userEvent.setup()
    render(
      <Input
        aria-label="Usuario"
        type="text"
        placeholder="tu usuario"
        aria-invalid
      />
    )

    const input = screen.getByLabelText("Usuario")
    expect(input).toHaveAttribute("type", "text")
    expect(input).toHaveAttribute("aria-invalid", "true")
    await ue.type(input, "admin")
    expect(input).toHaveValue("admin")
  })
})
