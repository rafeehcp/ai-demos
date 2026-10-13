import type { Citation } from "./api";

export type Segment = { kind: "text"; text: string } | { kind: "cite"; citation: Citation };

/**
 * Splits an answer into text and citation segments. A `[n]` marker becomes a
 * chip only when `citations` has that `n`; any other bracketed text stays text.
 */
export function parseAnswer(answer: string, citations: readonly Citation[]): Segment[] {
  const byNumber = new Map(citations.map((c) => [c.n, c]));
  const segments: Segment[] = [];
  let last = 0;

  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    const citation = byNumber.get(Number(match[1]));
    if (!citation) continue;
    if (match.index > last) segments.push({ kind: "text", text: answer.slice(last, match.index) });
    segments.push({ kind: "cite", citation });
    last = match.index + match[0].length;
  }
  if (last < answer.length) segments.push({ kind: "text", text: answer.slice(last) });
  return segments;
}
