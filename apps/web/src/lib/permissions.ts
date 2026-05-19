type RoleCarrier = {
  role?: string | null;
};

export function canViewGovernance(user: RoleCarrier | null | undefined) {
  return user?.role === "admin";
}
