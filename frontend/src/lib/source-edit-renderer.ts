import { cn } from '@/lib/utils'

export const sourceEditSourceMarkClassName = 'text-rose-600 line-through'

export const sourceEditReplacementClassName = 'text-rose-600 underline'

export const sourceEditActiveGroupClassName = 'rounded-sm bg-rose-50'

export function resolveSourceEditSourceMarkClassName(): string {
  return sourceEditSourceMarkClassName
}

export function resolveSourceEditReplacementClassName(): string {
  return sourceEditReplacementClassName
}

export function resolveSourceEditGroupClassName(
  annotationId: string,
  activeSourceAnnotationId: string | null | undefined,
): string {
  return cn(
    activeSourceAnnotationId === annotationId && sourceEditActiveGroupClassName,
  )
}
