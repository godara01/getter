import { describe, expect, it } from "vitest";

import { creditsLabel, rupees } from "../lib/razorpay";

describe("rupees", () => {
  it("uses Indian digit grouping", () => {
    expect(rupees(499)).toBe("₹499");
    expect(rupees(119900)).toBe("₹1,19,900");
  });
});

describe("creditsLabel", () => {
  it("handles singular, plural and zero", () => {
    expect(creditsLabel(0)).toBe("0 paid interviews");
    expect(creditsLabel(1)).toBe("1 paid interview");
    expect(creditsLabel(5)).toBe("5 paid interviews");
  });
});
