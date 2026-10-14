import { Toaster as Sonner } from 'sonner'

export function Toaster() {
  return (
    <Sonner
      position="top-center"
      richColors={false}
      closeButton={false}
      offset={20}
      toastOptions={{
        classNames: {
          toast:
            'rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-md',
        },
      }}
    />
  )
}
