import type { ComponentProps } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { OrganizationMemberRead, ProjectMemberRead } from "@/lib/api";

import { ProjectAccessTab } from "./project-access-tab";

const members: ProjectMemberRead[] = [
  { user_id: "user-owner", display_name: "Owner", role: "owner", source: "membership" },
  { user_id: "user-contributor", display_name: "Contributor", role: "contributor", source: "membership" },
];

const organizationMembers: OrganizationMemberRead[] = [
  {
    id: "user-owner",
    display_name: "Owner",
    email: "owner@example.test",
    role: "owner",
    is_billing_owner: true,
  },
  {
    id: "user-contributor",
    display_name: "Contributor",
    email: "contributor@example.test",
    role: "member",
    is_billing_owner: false,
  },
  {
    id: "user-reviewer",
    display_name: "Reviewer",
    email: "reviewer@example.test",
    role: "member",
    is_billing_owner: false,
  },
];

function renderAccessTab(overrides: Partial<ComponentProps<typeof ProjectAccessTab>> = {}) {
  const props = {
    projectId: "project-1",
    members,
    organizationMembers,
    canManageMembers: true,
    onAddMember: vi.fn().mockResolvedValue(undefined),
    onUpdateMember: vi.fn().mockResolvedValue(undefined),
    onRemoveMember: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };

  render(<ProjectAccessTab {...props} />);
  return props;
}

describe("ProjectAccessTab", () => {
  it("shows project members and lets an owner confirm removal", async () => {
    const props = renderAccessTab();

    expect(screen.getByText("Project access")).toBeDefined();
    expect(screen.getAllByText("Owner").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Contributor").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Add member" })).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Remove Contributor" }));
    expect(await screen.findByText("Remove project member?")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Remove member" }));

    await waitFor(() => {
      expect(props.onRemoveMember).toHaveBeenCalledWith("user-contributor");
    });
  });

  it("does not show membership mutation controls to a read-only collaborator", () => {
    renderAccessTab({ canManageMembers: false });

    expect(screen.getByText("Project access")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Add member" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Remove Contributor" })).toBeNull();
    expect(screen.queryByLabelText("Change role for Contributor")).toBeNull();
  });

  it("updates a member role from the project access table", async () => {
    const props = renderAccessTab();

    fireEvent.click(screen.getByLabelText("Change role for Contributor"));
    const managerOption = await screen.findByRole("option", { name: "Manager" });
    fireEvent.pointerDown(managerOption, { pointerType: "touch" });
    fireEvent.click(managerOption);

    await waitFor(() => {
      expect(props.onUpdateMember).toHaveBeenCalledWith("user-contributor", "manager");
    });
  });
});
