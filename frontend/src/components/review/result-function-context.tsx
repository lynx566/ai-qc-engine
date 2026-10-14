import type { ReactNode } from 'react'

import { getQcFlowPresentation } from '@/lib/launcher-presentation'
import {
  isResultFunctionViewQueryActive,
  type ResultFunctionViewQuery,
} from '@/lib/result-function-view-query'
import { resolveSemanticModuleDisplayLabel } from '@/lib/result-scope-state'
import { cn } from '@/lib/utils'

type ResultFunctionContextProps = {
  flowId: string
  functionViewQuery: ResultFunctionViewQuery | null
  availableSemanticModuleIds: readonly string[]
  onFunctionViewQueryChange: (query: ResultFunctionViewQuery) => void
  functionLabelAccessory?: ReactNode
  sectionContext?: ReactNode
}

const semanticModulePillClassName =
  'inline-flex h-6 shrink-0 items-center rounded-[4px] border px-2 text-[12px] font-medium transition-colors outline-none! focus:outline-none! focus-visible:outline-none!'

function semanticModulePillClassNameFor(isActive: boolean): string {
  return cn(
    semanticModulePillClassName,
    isActive
      ? 'border-[#91caff] bg-[#f0f5ff] text-[#2b5ae8]'
      : 'border-transparent bg-transparent text-[#64748B] hover:bg-[#f5f6f7] hover:text-[#475569]',
  )
}

export function ResultFunctionContext({
  flowId,
  functionViewQuery,
  availableSemanticModuleIds,
  onFunctionViewQueryChange,
  functionLabelAccessory,
  sectionContext,
}: ResultFunctionContextProps) {
  const functionLabel = getQcFlowPresentation(flowId).localizedName
  const showViewScopeSelector =
    functionViewQuery !== null && availableSemanticModuleIds.length >= 2
  const singleSemanticModuleId =
    availableSemanticModuleIds.length === 1 ? availableSemanticModuleIds[0] : null
  const singleSemanticModuleLabel = singleSemanticModuleId
    ? resolveSemanticModuleDisplayLabel(singleSemanticModuleId)
    : null

  return (
    <div data-result-function-context className="min-w-0">
      <div className="space-y-3">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex min-w-0 flex-1 items-center gap-1">
            <p
              data-result-function-label
              className="min-w-0 text-[14px] font-semibold leading-snug text-[#0F172A]"
            >
              {functionLabel}
            </p>
            {functionLabelAccessory}
          </div>
          {singleSemanticModuleId ? (
            <span
              data-result-function-scope-label
              data-semantic-module-id={singleSemanticModuleId}
              className={cn(semanticModulePillClassNameFor(true), 'pointer-events-none')}
              title={singleSemanticModuleLabel ?? undefined}
            >
              {singleSemanticModuleLabel}
            </span>
          ) : null}
        </div>
        {sectionContext}
        {showViewScopeSelector ? (
          <div
            data-result-function-view-query
            className="flex flex-wrap gap-1"
            role="group"
            aria-label="功能结果范围"
          >
            <button
              type="button"
              data-function-view-query-mode="all"
              aria-pressed={isResultFunctionViewQueryActive(functionViewQuery, { mode: 'all' })}
              className={semanticModulePillClassNameFor(
                isResultFunctionViewQueryActive(functionViewQuery, { mode: 'all' }),
              )}
              onClick={() => onFunctionViewQueryChange({ mode: 'all' })}
            >
              全部
            </button>
            {availableSemanticModuleIds.map((moduleId) => {
              const candidate: ResultFunctionViewQuery = {
                mode: 'semantic_module',
                semanticModuleId: moduleId,
              }
              const isActive = isResultFunctionViewQueryActive(functionViewQuery, candidate)
              return (
                <button
                  key={moduleId}
                  type="button"
                  data-function-view-query-mode="semantic_module"
                  data-semantic-module-id={moduleId}
                  aria-pressed={isActive}
                  className={semanticModulePillClassNameFor(isActive)}
                  onClick={() => onFunctionViewQueryChange(candidate)}
                >
                  {resolveSemanticModuleDisplayLabel(moduleId)}
                </button>
              )
            })}
          </div>
        ) : null}
      </div>
    </div>
  )
}
