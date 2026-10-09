import { useState } from "react"

import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "./dropdown-menu"

function FullMenu() {
  const [checked, setChecked] = useState(true)
  const [sede, setSede] = useState("smi")

  return (
    <DropdownMenu open onOpenChange={() => undefined}>
      <DropdownMenuTrigger asChild>
        <button type="button">Abrir menu</button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuGroup>
          <DropdownMenuLabel inset>Cuenta</DropdownMenuLabel>
          <DropdownMenuItem inset>Perfil</DropdownMenuItem>
          <DropdownMenuItem variant="destructive">Salir</DropdownMenuItem>
          <DropdownMenuShortcut>Ctrl+Q</DropdownMenuShortcut>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuCheckboxItem
          checked={checked}
          onCheckedChange={(value) => setChecked(value === true)}
        >
          Recordarme
        </DropdownMenuCheckboxItem>
        <DropdownMenuRadioGroup value={sede} onValueChange={setSede}>
          <DropdownMenuRadioItem value="smi">SMI</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="britanico">Britanico</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
        <DropdownMenuSub open>
          <DropdownMenuSubTrigger inset>Mas</DropdownMenuSubTrigger>
          <DropdownMenuPortal>
            <DropdownMenuSubContent>
              <DropdownMenuItem>Ayuda</DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuPortal>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

describe("DropdownMenu", () => {
  it("muestra items, checkbox, radios y submenu", async () => {
    const ue = userEvent.setup()
    render(<FullMenu />)

    expect(await screen.findByText("Cuenta")).toBeInTheDocument()
    expect(screen.getByText("Perfil")).toBeInTheDocument()
    expect(screen.getByText("Salir")).toBeInTheDocument()
    expect(screen.getByText("Ctrl+Q")).toBeInTheDocument()
    expect(screen.getByText("Recordarme")).toBeInTheDocument()
    expect(screen.getByText("SMI")).toBeInTheDocument()
    expect(screen.getByText("Britanico")).toBeInTheDocument()
    expect(screen.getByText("Ayuda")).toBeInTheDocument()

    await ue.click(screen.getByText("Britanico"))
    await ue.click(screen.getByText("Recordarme"))
    expect(screen.getByText("Ayuda")).toBeInTheDocument()
  })
})
