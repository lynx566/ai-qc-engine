import { cn } from '@/lib/utils'

type DocumentIdentityProps = {
  documentTypeLabel: string
  displayName: string
  className?: string
}

export function DocumentIdentity({
  documentTypeLabel,
  displayName,
  className,
}: DocumentIdentityProps) {
  const identity = `${documentTypeLabel} · ${displayName}`

  return (
    <p
      className={cn(
        'min-w-0 max-w-full whitespace-normal break-words text-[13px] font-medium text-[#667085]',
        className,
      )}
      aria-label={identity}
      title={identity}
      data-document-identity
    >
      {identity}
    </p>
  )
}
