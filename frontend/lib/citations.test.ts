import { describe, expect, it } from "vitest";
import type { Citation } from "./api";
import { parseAnswer } from "./citations";

const cite = (n: number, page = n): Citation => ({
  n,
  document_id: "d_1",
  document_name: "lease.pdf",
  page,
  quote: `quote ${n}`,
});

describe("parseAnswer", () => {
  it("turns known markers into chips between text", () => {
    const c1 = cite(1, 4);
    const c2 = cite(2, 5);
    expect(parseAnswer("Notice is 60 days [1]. A fee applies [2].", [c1, c2])).toEqual([
      { kind: "text", text: "Notice is 60 days " },
      { kind: "cite", citation: c1 },
      { kind: "text", text: ". A fee applies " },
      { kind: "cite", citation: c2 },
      { kind: "text", text: "." },
    ]);
  });

  it("keeps adjacent markers as separate chips with no empty text between", () => {
    const [c1, c2] = [cite(1), cite(2)];
    expect(parseAnswer("[1][2]", [c1, c2])).toEqual([
      { kind: "cite", citation: c1 },
      { kind: "cite", citation: c2 },
    ]);
  });

  it("leaves markers with no matching citation as literal text", () => {
    const c1 = cite(1);
    expect(parseAnswer("See [3] and [1], not [x] or [ 1 ].", [c1])).toEqual([
      { kind: "text", text: "See [3] and " },
      { kind: "cite", citation: c1 },
      { kind: "text", text: ", not [x] or [ 1 ]." },
    ]);
  });

  it("returns the whole answer as text when there are no citations", () => {
    const answer = "The documents don't say [1].";
    expect(parseAnswer(answer, [])).toEqual([{ kind: "text", text: answer }]);
  });

  it("returns nothing for an empty answer", () => {
    expect(parseAnswer("", [cite(1)])).toEqual([]);
  });
});
