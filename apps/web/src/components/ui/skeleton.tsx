import { cn } from "@/lib/utils"

function Skeleton({ className, shimmer = true, ...props }: React.ComponentProps<"div"> & { shimmer?: boolean }) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "relative overflow-hidden rounded-md bg-muted",
        shimmer ? "before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_2s_ease-in-out_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/10 before:to-transparent" : "animate-pulse",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
