/** Product contract for Launcher / QC Setup slot file selection (single .docx). */
export function isAcceptedSlotUploadFile(file: File): boolean {
  const normalizedName = file.name.trim().toLowerCase()
  return normalizedName.endsWith('.docx') && normalizedName.length > '.docx'.length
}
