import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { ThemeToggle } from "./ThemeToggle"

describe("ThemeToggle", () => {
  it("alterna modo claro/oscuro", async () => {
    const ue = userEvent.setup()
    render(<ThemeToggle />)

    const button = screen.getByRole("button", { name: /modo/i })
    await ue.click(button)
    expect(document.documentElement.classList.contains("dark")).toBe(true)
    await ue.click(screen.getByRole("button", { name: /modo/i }))
    expect(document.documentElement.classList.contains("dark")).toBe(false)
  })
})
