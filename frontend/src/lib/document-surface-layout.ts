/** Horizontal canvas inset for the centered canonical reader and its toolbar. */
export const centeredDocumentCanvasHorizontalClassName =
  'justify-center px-2 min-[840px]:px-4 min-[840px]:sm:px-8'

/** Full Document stays fluid below 840px and caps the centered surface above it. */
export const fullDocumentSurfaceMaxWidthClassName = 'min-[840px]:max-w-[56rem]'

/**
 * Canonical document page content box. Extract does not carry section margins;
 * use symmetric, fluid page whitespace independently of paragraph indents.
 * The article is the sole owner; canvas padding only separates it from the UI.
 */
export const documentPageHorizontalInsetClassName = 'px-[clamp(1.5rem,10%,6rem)]'
