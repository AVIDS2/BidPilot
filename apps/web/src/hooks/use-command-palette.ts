import { useState, useCallback, useEffect } from "react"

export function useCommandPalette() {
  const [open, setOpen] = useState(false)

  const toggle = useCallback(() => {
    setOpen((prev) => !prev)
  }, [])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        toggle()
      }
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [toggle])

  return { open, setOpen, toggle }
}
