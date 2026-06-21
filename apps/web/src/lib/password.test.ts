import { describe, expect, it } from "vitest";

import { isStrongPassword } from "./password";

describe("isStrongPassword", () => {
  it("requires at least 8 characters, one uppercase letter, one lowercase letter, and one digit", () => {
    expect(isStrongPassword("Password1")).toBe(true);
    expect(isStrongPassword("password1")).toBe(false);
    expect(isStrongPassword("PASSWORD1")).toBe(false);
    expect(isStrongPassword("Password")).toBe(false);
    expect(isStrongPassword("Pa1")).toBe(false);
  });
});
