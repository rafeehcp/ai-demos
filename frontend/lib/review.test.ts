import { describe, expect, it } from "vitest";
import type { ClauseKind, ContractReview, ReviewResponse } from "./api";
import { currentStep, exportFileName, exportJson, groupClauses, reviewSteps } from "./review";

const clause = (kind: ClauseKind, title: string): ContractReview["clauses"][number] => ({
  kind,
  title,
  plain_english: "...",
  evidence: { page: 1, quote: "q", verified: true },
});

describe("groupClauses", () => {
  it("orders groups by clause kind, keeps order within a kind, and drops empty kinds", () => {
    const groups = groupClauses([
      clause("other", "Pets"),
      clause("governing_law", "Law"),
      clause("termination", "Early exit"),
      clause("other", "Access"),
      clause("termination", "Landlord exit"),
    ]);
    expect(groups.map((g) => [g.label, g.clauses.map((c) => c.title)])).toEqual([
      ["Termination", ["Early exit", "Landlord exit"]],
      ["Governing law", ["Law"]],
      ["Other clauses", ["Pets", "Access"]],
    ]);
  });

  it("returns no groups for no clauses", () => {
    expect(groupClauses([])).toEqual([]);
  });
});

describe("review steps", () => {
  it("names the page count when it is known", () => {
    expect(reviewSteps(12)[0]).toBe("Reading 12 pages");
    expect(reviewSteps(1)[0]).toBe("Reading 1 page");
    expect(reviewSteps(null)[0]).toBe("Reading the contract");
  });

  it("advances on the timer and stays on the last step", () => {
    expect([0, 2_999, 3_000, 17_999, 18_000, 600_000].map(currentStep)).toEqual([0, 0, 1, 1, 2, 2]);
  });
});

describe("JSON export", () => {
  it("names the file after the contract", () => {
    expect(exportFileName("lease.pdf")).toBe("lease-review.json");
    expect(exportFileName("Acme MSA (final).PDF")).toBe("Acme-MSA-final-review.json");
    expect(exportFileName(".pdf")).toBe("contract-review.json");
  });

  it("round-trips the whole response, verification flags included", () => {
    const result: ReviewResponse = {
      document_name: "lease.pdf",
      pages: 3,
      review: {
        summary: "A lease.",
        contract_type: "Residential lease",
        parties: [{ name: "Harbor Homes LLC", role: "Landlord" }],
        key_terms: [],
        clauses: [clause("payment", "Rent")],
        risks: [
          { severity: "high", title: "Fee", explanation: "...", evidence: { page: 2, quote: "q", verified: false } },
        ],
      },
    };
    expect(JSON.parse(exportJson(result))).toEqual(result);
  });
});
