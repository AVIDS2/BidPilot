import * as React from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { Command } from "cmdk"
import {
  LayoutDashboardIcon,
  FileTextIcon,
  CreditCardIcon,
  PlusIcon,
  SearchIcon,
  SettingsIcon,
  UserIcon,
  MoonIcon,
  SunIcon,
} from "lucide-react"
import { useTheme } from "next-themes"

type CommandPaletteProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { theme, setTheme } = useTheme()
  const inputRef = React.useRef<HTMLInputElement>(null)

  const runAction = React.useCallback(
    (action: () => void) => {
      onOpenChange(false)
      action()
    },
    [onOpenChange]
  )

  return (
    <>
      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/10 supports-backdrop-filter:backdrop-blur-xs"
          onClick={() => onOpenChange(false)}
        />
      )}

      {/* Dialog */}
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed top-[20%] left-1/2 z-50 w-full max-w-[calc(100%-2rem)] -translate-x-1/2 sm:max-w-lg"
        >
          <Command
            className="rounded-xl bg-popover text-popover-foreground ring-1 ring-foreground/10 shadow-lg overflow-hidden"
            onKeyDown={(e: React.KeyboardEvent) => {
              if (e.key === "Escape") {
                onOpenChange(false)
              }
            }}
          >
            <div className="flex items-center border-b px-3">
              <SearchIcon className="size-4 shrink-0 text-muted-foreground" />
              <Command.Input
                ref={inputRef}
                autoFocus
                placeholder={t("commandPalette.placeholder")}
                className="flex h-11 w-full rounded-md bg-transparent py-3 pl-2 pr-3 text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex">
                ESC
              </kbd>
            </div>

            <Command.List className="max-h-[300px] overflow-y-auto overflow-x-hidden p-1">
              <Command.Empty className="py-6 text-center text-sm text-muted-foreground">
                {t("commandPalette.noResults")}
              </Command.Empty>

              {/* Navigation Group */}
              <Command.Group
                heading={t("commandPalette.groups.navigation")}
                className="px-2 py-1.5 text-xs font-medium text-muted-foreground [&>[cmdk-group-heading]]:px-2 [&>[cmdk-group-heading]]:py-1.5"
              >
                <CommandItem
                  icon={<LayoutDashboardIcon />}
                  label={t("nav.dashboard")}
                  shortcut="G D"
                  onSelect={() => runAction(() => navigate("/dashboard"))}
                />
                <CommandItem
                  icon={<FileTextIcon />}
                  label={t("nav.projects")}
                  shortcut="G P"
                  onSelect={() => runAction(() => navigate("/projects"))}
                />
                <CommandItem
                  icon={<CreditCardIcon />}
                  label={t("nav.pricing")}
                  onSelect={() => runAction(() => navigate("/pricing"))}
                />
                <CommandItem
                  icon={<UserIcon />}
                  label={t("nav.account")}
                  onSelect={() => runAction(() => navigate("/account"))}
                />
                <CommandItem
                  icon={<SettingsIcon />}
                  label={t("nav.settings", { defaultValue: "Provider Settings" })}
                  onSelect={() => runAction(() => navigate("/settings/providers"))}
                />
              </Command.Group>

              {/* Actions Group */}
              <Command.Separator className="mx-2 my-1 h-px bg-border" />
              <Command.Group
                heading={t("commandPalette.groups.actions")}
                className="px-2 py-1.5 text-xs font-medium text-muted-foreground [&>[cmdk-group-heading]]:px-2 [&>[cmdk-group-heading]]:py-1.5"
              >
                <CommandItem
                  icon={<PlusIcon />}
                  label={t("commandPalette.actions.newProject")}
                  shortcut="N"
                  onSelect={() => runAction(() => navigate("/projects"))}
                />
                <CommandItem
                  icon={theme === "dark" ? <SunIcon /> : <MoonIcon />}
                  label={t("commandPalette.actions.toggleTheme")}
                  onSelect={() =>
                    runAction(() => setTheme(theme === "dark" ? "light" : "dark"))
                  }
                />
              </Command.Group>
            </Command.List>

            <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
              <span>{t("commandPalette.hint.navigate")}</span>
              <span>{t("commandPalette.hint.select")}</span>
            </div>
          </Command>
        </div>
      )}
    </>
  )
}

function CommandItem({
  icon,
  label,
  shortcut,
  onSelect,
}: {
  icon: React.ReactNode
  label: string
  shortcut?: string
  onSelect: () => void
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="relative flex cursor-pointer select-none items-center gap-3 rounded-md px-2 py-2 text-sm outline-none aria-selected:bg-accent aria-selected:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
    >
      <span className="flex size-5 shrink-0 items-center justify-center text-muted-foreground [&>svg]:size-4">
        {icon}
      </span>
      <span className="flex-1 truncate">{label}</span>
      {shortcut && (
        <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:flex">
          {shortcut}
        </kbd>
      )}
    </Command.Item>
  )
}
