import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { Button } from "./button"

describe("Button", () => {
  it("dispara el click y acepta variantes", async () => {
    const onClick = vi.fn()
    const ue = userEvent.setup()
    render(
      <Button variant="outline" size="sm" onClick={onClick}>
        Guardar
      </Button>
    )

    const button = screen.getByRole("button", { name: "Guardar" })
    expect(button.tagName).toBe("BUTTON")
    await ue.click(button)
    expect(onClick).toHaveBeenCalled()
  })

  it("delega el markup cuando asChild es true", () => {
    render(
      <Button asChild variant="link" size="lg">
        <a href="/kpis">Ir a KPIs</a>
      </Button>
    )

    const link = screen.getByRole("link", { name: "Ir a KPIs" })
    expect(link).toHaveAttribute("href", "/kpis")
    expect(link).toHaveAttribute("data-slot", "button")
  })
})
