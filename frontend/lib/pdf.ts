/**
 * Page count from the raw bytes, or null when it can't be seen. PDFs that
 * keep their page objects in compressed streams hide them from this scan.
 */
export async function countPdfPages(file: Blob): Promise<number | null> {
  const text = new TextDecoder("latin1").decode(await file.arrayBuffer());
  return text.match(/\/Type\s*\/Page(?![a-zA-Z])/g)?.length ?? null;
}
