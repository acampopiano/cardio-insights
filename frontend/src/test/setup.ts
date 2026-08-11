import "@testing-library/jest-dom/vitest"

import { afterEach } from "vitest"
import { cleanup } from "@testing-library/react"

if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = function scrollTo() {
    /* jsdom stub */
  }
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})
