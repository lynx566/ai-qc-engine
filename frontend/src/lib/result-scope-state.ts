import { composeDocumentBlockId } from '@/adapters/extract-document'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

export function resolveResultScopeHeadingTitle(
  scopeResult: InternalResultScopeResult,
  document: DocumentView,
): string {
  const outlineBlockId = composeDocumentBlockId(
    scopeResult.docId,
    scopeResult.outlineHeadingBlockId,
  )
  const outlineBlock = document.blocks.find((block) => block.blockId === outlineBlockId)
  const fromOutlineBlock = outlineBlock?.displayText?.trim()
  if (fromOutlineBlock) {
    return fromOutlineBlock
  }

  const fromHeadingPath = scopeResult.headingPath.at(-1)?.trim()
  if (fromHeadingPath) {
    return fromHeadingPath
  }

  return '未命名章节'
}

export function buildScopeResultByOutlineBlockId(
  scopeResults: readonly InternalResultScopeResult[],
): Map<string, InternalResultScopeResult> {
  const index = new Map<string, InternalResultScopeResult>()
  for (const scopeResult of scopeResults) {
    if (!scopeResult.hasSuccessfulCheck) {
      continue
    }
    const readerBlockId = composeDocumentBlockId(
      scopeResult.docId,
      scopeResult.outlineHeadingBlockId,
    )
    index.set(readerBlockId, scopeResult)
  }
  return index
}

export function buildScopeResultsByOutlineBlockId(
  scopeResults: readonly InternalResultScopeResult[],
): Map<string, InternalResultScopeResult[]> {
  const index = new Map<string, InternalResultScopeResult[]>()
  for (const scopeResult of scopeResults) {
    if (!scopeResult.hasSuccessfulCheck) {
      continue
    }
    const readerBlockId = composeDocumentBlockId(
      scopeResult.docId,
      scopeResult.outlineHeadingBlockId,
    )
    const group = index.get(readerBlockId)
    if (group) {
      group.push(scopeResult)
    } else {
      index.set(readerBlockId, [scopeResult])
    }
  }
  return index
}

export function resolveActiveProjectedScopeResultsForOutlineBlock(
  scopeResultsByOutlineBlockId: ReadonlyMap<string, InternalResultScopeResult[]>,
  outlineBlockId: string | null,
): InternalResultScopeResult[] {
  if (!outlineBlockId) {
    return []
  }
  return scopeResultsByOutlineBlockId.get(outlineBlockId) ?? []
}

export function resolveActiveScopeResultForOutlineBlock(
  scopeResultByOutlineBlockId: ReadonlyMap<string, InternalResultScopeResult>,
  outlineBlockId: string | null,
): InternalResultScopeResult | null {
  if (!outlineBlockId) {
    return null
  }
  return scopeResultByOutlineBlockId.get(outlineBlockId) ?? null
}

export function resolveOutlineSectionTitle(
  outlineBlockId: string,
  document: DocumentView,
): string {
  const outlineBlock = document.blocks.find((block) => block.blockId === outlineBlockId)
  const fromOutlineBlock = outlineBlock?.displayText?.trim()
  if (fromOutlineBlock) {
    return fromOutlineBlock
  }
  const fromHeadingPath = outlineBlock?.headingPath.at(-1)?.trim()
  if (fromHeadingPath) {
    return fromHeadingPath
  }
  return '未命名章节'
}

/** Aligns with candidate-scope `content_domain_id` / scope `semanticModuleId`. */
const SEMANTIC_MODULE_DISPLAY_LABEL_BY_ID: Record<string, string> = {
  clinical_safety: '临床安全性',
}

export function resolveSemanticModuleDisplayLabel(semanticModuleId: string): string {
  return SEMANTIC_MODULE_DISPLAY_LABEL_BY_ID[semanticModuleId] ?? semanticModuleId
}

export function resolveResultSemanticModuleLabels(
  scopeResults: readonly InternalResultScopeResult[],
): string[] {
  const labels: string[] = []
  const seen = new Set<string>()
  for (const scopeResult of scopeResults) {
    if (!scopeResult.hasSuccessfulCheck) {
      continue
    }
    const label = resolveSemanticModuleDisplayLabel(scopeResult.semanticModuleId)
    if (seen.has(label)) {
      continue
    }
    seen.add(label)
    labels.push(label)
  }
  return labels
}

export function resolveInitialActiveScope(
  scopeResults: readonly InternalResultScopeResult[],
): InternalResultScopeResult | null {
  return scopeResults.find((scope) => scope.hasSuccessfulCheck) ?? null
}

export function resolveInitialOutlineBlockId(
  outlineEntries: readonly DocumentOutlineEntry[],
  activeScope: InternalResultScopeResult | null,
): string | null {
  if (activeScope) {
    return composeDocumentBlockId(activeScope.docId, activeScope.outlineHeadingBlockId)
  }
  return outlineEntries[0]?.blockId ?? null
}
