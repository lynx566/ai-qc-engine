// @vitest-environment happy-dom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { LauncherPageCard, LauncherPageShell } from '@/components/launcher/launcher-page-shell'
import {
  LAUNCHER_PRODUCT_TITLE,
  LAUNCHER_PRODUCT_VERSION,
} from '@/lib/launcher-presentation'

describe('launcher page shell', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('renders product title, version, background, and max width container', () => {
    act(() => {
      root.render(
        createElement(
          LauncherPageShell,
          null,
          createElement(LauncherPageCard, null, 'shell content'),
        ),
      )
    })

    expect(container.textContent).toContain(LAUNCHER_PRODUCT_TITLE)
    expect(container.textContent).toContain(LAUNCHER_PRODUCT_VERSION)
    expect(container.querySelector('.launcher-tech-bg')).not.toBeNull()
    expect(container.querySelector('.max-w-5xl')).not.toBeNull()
    expect(container.innerHTML).toContain('rounded-2xl')
    expect(container.innerHTML).toContain('border-[#E2E8F0]')
    expect(container.innerHTML).toContain('bg-[#F1F5F9]')
    expect(container.innerHTML).toContain('text-[#2563EB]')
    expect(container.innerHTML).not.toContain('size-9 shrink-0 items-center justify-center rounded-lg')
    expect(container.textContent).toContain('shell content')
  })

  it('keeps launcher using shared shell instead of local duplicate', () => {
    const launcherSource = readFileSync(resolve(import.meta.dirname, 'launcher.tsx'), 'utf8')

    expect(launcherSource).toContain("from '@/components/launcher/launcher-page-shell'")
    expect(launcherSource).toContain('LauncherPageShell')
    expect(launcherSource).toContain('LauncherPageCard')
    expect(launcherSource).not.toContain('function LauncherPageShell')
    expect(launcherSource).not.toContain('function LauncherAnimatedBackground')
  })
})
