import { describe, expect, it, vi } from "vitest";

import { randomId } from "@/utils/randomId";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe("randomId", () => {
  it("returns uuid v4 shape", () => {
    expect(randomId()).toMatch(UUID_RE);
  });

  it("falls back when randomUUID throws (non-secure context)", () => {
    const original = globalThis.crypto.randomUUID;
    vi.spyOn(globalThis.crypto, "randomUUID").mockImplementation(() => {
      throw new DOMException("The operation is insecure.", "SecurityError");
    });
    try {
      expect(randomId()).toMatch(UUID_RE);
    } finally {
      globalThis.crypto.randomUUID = original;
    }
  });
});
