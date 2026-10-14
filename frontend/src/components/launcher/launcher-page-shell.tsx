import type { ReactNode } from 'react'
import { FileCheck2 } from 'lucide-react'
import { cn } from 'cn'

import {
  LAUNCHER_PRODUCT_TITLE,
  LAUNCHER_PRODUCT_VERSION,
} from '@/lib/launcher-presentation'

function LauncherAnimatedBackground() {
  return (
    <div aria-hidden="true" className="launcher-tech-bg pointer-events-none absolute inset-0">
      <div className="launcher-tech-mesh-a" />
      <div className="launcher-tech-mesh-b" />
      <div className="launcher-tech-mesh-c" />
    </div>
  )
}

type LauncherPageShellProps = {
  children: ReactNode
}

export function LauncherPageShell({ children }: LauncherPageShellProps) {
  return (
    <div className="relative flex min-h-svh flex-col">
      <LauncherAnimatedBackground />
      <header className="relative z-10 w-full">
        <div className="flex items-center gap-3.5 py-5 pl-10">
          <FileCheck2
            className="size-[1.375rem] shrink-0 text-[#2563EB]"
            strokeWidth={2}
            aria-hidden="true"
          />
          <div className="flex min-w-0 items-center gap-2.5">
            <h1 className="text-[1.35rem] font-bold tracking-tight text-[#1E293B]">
              {LAUNCHER_PRODUCT_TITLE}
            </h1>
            <span
              className="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-xs font-medium text-[#64748B] bg-[#F1F5F9]"
            >
              {LAUNCHER_PRODUCT_VERSION}
            </span>
          </div>
        </div>
      </header>
      <div className="relative z-10 flex-1 px-6 pt-18 pb-10 sm:px-8 sm:pt-20 sm:pb-12">
        <div className="mx-auto w-full max-w-5xl">{children}</div>
      </div>
    </div>
  )
}

type LauncherPageCardProps = {
  children: ReactNode
  className?: string
}

export function LauncherPageCard({ children, className }: LauncherPageCardProps) {
  return (
    <div
      className={cn(
        'w-full rounded-2xl border border-[#E2E8F0] bg-white px-8 py-10 shadow-[0_4px_20px_-2px_rgba(0,0,0,0.05)] sm:px-12 sm:py-12',
        className,
      )}
    >
      {children}
    </div>
  )
}
