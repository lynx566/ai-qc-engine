import { ChevronDown, ChevronUp, Info } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  resultReviewContainerBorderClassName,
  resultReviewInternalSeparatorSurfaceClassName,
} from '@/lib/result-review-visual-tokens'
import { cn } from '@/lib/utils'

export const SOURCE_ANNOTATION_HELP_USAGE_LEAD = '左键选中文字可进行修订或批注，'
export const SOURCE_ANNOTATION_HELP_USAGE_TAIL = '目前仅支持单句内选中。'

export const SOURCE_ANNOTATION_HELP_USAGE_SENTENCE =
  `${SOURCE_ANNOTATION_HELP_USAGE_LEAD}${SOURCE_ANNOTATION_HELP_USAGE_TAIL}`

export const SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE =
  '进行修订或批注不会直接改动上传的源文件，可点击“完整文档”查看全部审阅痕迹。'

const sourceAnnotationHelpSentenceClassName =
  'max-w-[16em] text-xs font-normal leading-snug'

function SourceAnnotationInfoTrigger({ className }: { className?: string }) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            className={cn(
              'shrink-0 text-muted-foreground hover:text-foreground',
              className,
            )}
            aria-label="原文标注说明"
            data-source-annotation-help="true"
          >
            <Info className="size-3.5" aria-hidden="true" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="start" className="max-w-none w-max">
          <div
            className="w-max max-w-[calc(100vw-2rem)] space-y-1.5"
            data-source-annotation-help-content="true"
          >
            <p className={sourceAnnotationHelpSentenceClassName}>
              <span className="block">{SOURCE_ANNOTATION_HELP_USAGE_LEAD}</span>
              <span className="block">{SOURCE_ANNOTATION_HELP_USAGE_TAIL}</span>
            </p>
            <p className={cn(sourceAnnotationHelpSentenceClassName, 'font-semibold')}>
              {SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE}
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

type AnnotationKindGroupProps = {
  kind: 'revision' | 'comment'
  total: number
  activeIndex: number | null
  onPrevious: () => void
  onNext: () => void
}

function resolveGroupLabel(total: number, activeIndex: number | null, label: string): string {
  if (activeIndex === null) {
    return `${label} ${total}`
  }
  return `${label} ${activeIndex + 1}/${total}`
}

function SourceAnnotationLabel({
  kind,
  total,
  activeIndex = null,
}: {
  kind: 'revision' | 'comment'
  total: number
  activeIndex?: number | null
}) {
  return (
    <span
      className="shrink-0 tabular-nums whitespace-nowrap text-[13px] text-foreground"
      data-source-annotation-label={kind}
    >
      {resolveGroupLabel(total, activeIndex, kind === 'revision' ? '修订' : '批注')}
    </span>
  )
}

export function SourceAnnotationContext({ revisionTotal, commentTotal }: {
  revisionTotal: number
  commentTotal: number
}) {
  return (
    <div
      data-source-annotation-context="true"
      className={cn(
        'flex h-7 flex-wrap items-center gap-2 rounded-[4px] border bg-muted/30 px-2 text-[13px] text-foreground',
        resultReviewContainerBorderClassName,
      )}
    >
      <SourceAnnotationLabel kind="revision" total={revisionTotal} />
      <span
        className={cn('h-3 w-px shrink-0', resultReviewInternalSeparatorSurfaceClassName)}
        aria-hidden="true"
        data-source-annotation-context-separator="true"
      />
      <div
        className="inline-flex items-center gap-0.5"
        data-source-annotation-comment-with-help="true"
      >
        <SourceAnnotationLabel kind="comment" total={commentTotal} />
        <SourceAnnotationInfoTrigger className="size-5 text-foreground hover:text-foreground/80" />
      </div>
    </div>
  )
}

function AnnotationKindGroup({
  kind,
  total,
  activeIndex,
  onPrevious,
  onNext,
}: AnnotationKindGroupProps) {
  const previousAriaLabel = kind === 'revision' ? '上一条修订' : '上一条批注'
  const nextAriaLabel = kind === 'revision' ? '下一条修订' : '下一条批注'

  return (
    <div
      className="inline-flex items-center gap-1.5 text-sm text-foreground"
      data-source-annotation-group-controls={kind}
    >
      <SourceAnnotationLabel
        kind={kind}
        total={total}
        activeIndex={activeIndex}
      />

      <div
        className={cn(
          'inline-flex w-5 shrink-0 flex-col overflow-hidden rounded-[3px] border bg-background',
          resultReviewContainerBorderClassName,
        )}
        data-source-annotation-nav={kind}
      >
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="h-3 min-h-3 w-full min-w-0 rounded-none p-0 text-foreground [&_svg]:size-3"
          disabled={total === 0}
          aria-label={previousAriaLabel}
          data-source-annotation-nav-previous={kind}
          onClick={onPrevious}
        >
          <ChevronUp aria-hidden="true" />
        </Button>
        <span
          className={cn('h-px w-full shrink-0', resultReviewInternalSeparatorSurfaceClassName)}
          aria-hidden="true"
        />
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="h-3 min-h-3 w-full min-w-0 rounded-none p-0 text-foreground [&_svg]:size-3"
          disabled={total === 0}
          aria-label={nextAriaLabel}
          data-source-annotation-nav-next={kind}
          onClick={onNext}
        >
          <ChevronDown aria-hidden="true" />
        </Button>
      </div>
    </div>
  )
}

export type SourceAnnotationNavigatorProps = {
  revisionTotal: number
  revisionActiveIndex: number | null
  commentTotal: number
  commentActiveIndex: number | null
  onRevisionPrevious: () => void
  onRevisionNext: () => void
  onCommentPrevious: () => void
  onCommentNext: () => void
}

export function SourceAnnotationNavigator({
  revisionTotal,
  revisionActiveIndex,
  commentTotal,
  commentActiveIndex,
  onRevisionPrevious,
  onRevisionNext,
  onCommentPrevious,
  onCommentNext,
}: SourceAnnotationNavigatorProps) {
  return (
    <div
      data-source-annotation-navigator="true"
      className="flex flex-wrap items-center gap-2 text-sm sm:gap-2"
    >
      <div data-source-annotation-group="revision">
        <AnnotationKindGroup
          kind="revision"
          total={revisionTotal}
          activeIndex={revisionActiveIndex}
          onPrevious={onRevisionPrevious}
          onNext={onRevisionNext}
        />
      </div>
      <div data-source-annotation-group="comment">
        <AnnotationKindGroup
          kind="comment"
          total={commentTotal}
          activeIndex={commentActiveIndex}
          onPrevious={onCommentPrevious}
          onNext={onCommentNext}
        />
      </div>
    </div>
  )
}
