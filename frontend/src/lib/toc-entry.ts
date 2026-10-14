/** Normalize Word TOC style levels (e.g. ``TOC 11`` → 1, ``TOC 21`` → 2). */
export function normalizeTocOutlineLevel(tocLevel?: number): number {
  if (!tocLevel || tocLevel < 1) {
    return 1
  }

  if (tocLevel >= 10) {
    return Math.floor(tocLevel / 10)
  }

  return tocLevel
}

export type ParsedTocEntry = {
  title: string
  pageNumber?: string
}

/** Split a TOC line into title and trailing page number (tab or space separated). */
export function parseTocEntryText(text: string): ParsedTocEntry {
  const tabIndex = text.indexOf('\t')
  if (tabIndex >= 0) {
    const title = text.slice(0, tabIndex).trimEnd()
    const pageNumber = text.slice(tabIndex + 1).trim()
    return pageNumber ? { title, pageNumber } : { title }
  }

  const match = text.match(/^(.+?)\s+(\d+)\s*$/)
  if (match) {
    return { title: match[1]!.trimEnd(), pageNumber: match[2] }
  }

  return { title: text }
}
