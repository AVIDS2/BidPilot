import { describe, expect, it } from "vitest";
import { assistantContextForLocation } from "./assistant-route-context";

describe("assistantContextForLocation", () => {
  it("binds the assistant to the project detail route", () => {
    expect(assistantContextForLocation("/projects/project-123")).toEqual({
      page: "/projects/project-123",
      projectId: "project-123",
    });
  });

  it("keeps global pages unscoped unless the Agent target is explicit", () => {
    expect(assistantContextForLocation("/dashboard")).toEqual({ page: "/dashboard" });
    expect(assistantContextForLocation("/agent", "?project=project-456")).toEqual({
      page: "/agent",
      projectId: "project-456",
    });
  });
});
