import { CLAUSE_KINDS, type ClauseKind, type ContractReview, type ReviewResponse, type Severity } from "./api";

export const CLAUSE_LABELS: Record<ClauseKind, string> = {
  termination: "Termination",
  renewal: "Renewal",
  payment: "Payment",
  liability: "Liability",
  indemnity: "Indemnity",
  confidentiality: "Confidentiality",
  intellectual_property: "Intellectual property",
  governing_law: "Governing law",
  dispute_resolution: "Disputes",
  non_compete: "Non-compete",
  other: "Other clauses",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  high: "High risk",
  medium: "Medium risk",
  low: "Low risk",
};

type Clause = ContractReview["clauses"][number];

/** Clauses grouped by kind, groups in the fixed CLAUSE_KINDS order, empty kinds left out. */
export function groupClauses(clauses: Clause[]): { kind: ClauseKind; label: string; clauses: Clause[] }[] {
  return CLAUSE_KINDS.flatMap((kind) => {
    const inKind = clauses.filter((c) => c.kind === kind);
    return inKind.length ? [{ kind, label: CLAUSE_LABELS[kind], clauses: inKind }] : [];
  });
}

/**
 * The review is one request, so these steps run on a timer and only
 * approximate what the server is doing. The last step stays current until
 * the response arrives.
 */
export const STEP_STARTS_MS = [0, 3_000, 18_000] as const;

export function reviewSteps(pages: number | null): string[] {
  const reading = pages === null ? "Reading the contract" : `Reading ${pages} ${pages === 1 ? "page" : "pages"}`;
  return [reading, "Reviewing clauses", "Checking quotes"];
}

export function currentStep(elapsedMs: number): number {
  return STEP_STARTS_MS.findLastIndex((start) => elapsedMs >= start);
}

export function exportFileName(documentName: string): string {
  const base = documentName.replace(/\.pdf$/i, "").replace(/[^\w.-]+/g, "-").replace(/^-+|-+$/g, "");
  return `${base || "contract"}-review.json`;
}

export function exportJson(result: ReviewResponse): string {
  return JSON.stringify(result, null, 2) + "\n";
}
