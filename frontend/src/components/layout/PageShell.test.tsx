import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { PageShell } from "./PageShell"

describe("PageShell", () => {
  it("aplica el contenedor estandar max-w-6xl", () => {
    const { container } = render(
      <PageShell>
        <p>contenido</p>
      </PageShell>
    )
    expect(screen.getByText("contenido")).toBeInTheDocument()
    expect(container.firstChild).toHaveClass("max-w-6xl", "px-4", "py-6", "sm:px-6")
  })
})
