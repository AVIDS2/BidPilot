import { describe, expect, it } from "vitest";
import { getRegistrationErrorKey } from "./registration-errors";

describe("getRegistrationErrorKey", () => {
  it("maps duplicate organization slugs to a specific user-facing message", () => {
    const error = new Error(
      'API 400: {"detail":"An organization with this slug already exists"}',
    );

    expect(getRegistrationErrorKey(error)).toBe("toast.orgSlugExists");
  });

  it("keeps duplicate email registration specific", () => {
    const error = new Error('API 400: {"detail":"Email already registered"}');

    expect(getRegistrationErrorKey(error)).toBe("toast.emailExists");
  });
});
