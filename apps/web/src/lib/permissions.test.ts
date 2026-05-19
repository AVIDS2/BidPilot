import { describe, expect, it } from "vitest";
import { canViewGovernance } from "./permissions";

describe("canViewGovernance", () => {
  it("allows admin users to view governance surfaces", () => {
    expect(canViewGovernance({ role: "admin" })).toBe(true);
  });

  it("denies non-admin users", () => {
    expect(canViewGovernance({ role: "member" })).toBe(false);
    expect(canViewGovernance({ role: "user" })).toBe(false);
  });

  it("denies missing users", () => {
    expect(canViewGovernance(null)).toBe(false);
    expect(canViewGovernance(undefined)).toBe(false);
  });
});
