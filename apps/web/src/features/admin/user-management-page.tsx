import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listUsers, updateUserRole, setUserStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, UserIcon, ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

const ROLE_OPTIONS = [
  { label: "Admin", value: "admin" },
  { label: "Member", value: "member" },
];

function UserManagementSkeleton() {
  return (
    <div className="mx-auto max-w-5xl py-8">
      <div className="flex items-center gap-3 mb-6">
        <Skeleton className="size-6" />
        <Skeleton className="h-8 w-48" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-24" />
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-8 w-32" />
                <Skeleton className="h-8 w-48" />
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function UserManagementPage() {
  const { user: currentUser } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [jumpInput, setJumpInput] = useState("");
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryFn: () => listUsers(page, pageSize),
    queryKey: ["admin-users", page],
  });

  const roleMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateUserRole(userId, role),
    onSuccess: () => {
      toast.success("Role updated");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error("Failed to update role"),
  });

  const statusMut = useMutation({
    mutationFn: ({ userId, disabled }: { userId: string; disabled: boolean }) =>
      setUserStatus(userId, disabled),
    onSuccess: (_, vars) => {
      toast.success(vars.disabled ? "User disabled" : "User re-enabled");
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error("Failed to update status"),
  });

  if (isLoading) return <UserManagementSkeleton />;

  if (currentUser?.role !== "admin") {
    return (
      <div className="mx-auto max-w-5xl py-8">
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <ShieldIcon className="mx-auto size-10 mb-3 opacity-40" />
            <p>Admin access required.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const users = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  return (
    <div className="mx-auto max-w-5xl py-8">
      <div className="flex items-center gap-3 mb-6">
        <UsersIcon className="size-6" />
        <h1 className="text-2xl font-bold tracking-tight">User Management</h1>
        <Badge variant="secondary">{total} users</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
        </CardHeader>
        <CardContent>
          {!users.length ? (
            <Empty className="min-h-32">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <UsersIcon />
                </EmptyMedia>
                <EmptyTitle>No users found</EmptyTitle>
                <EmptyDescription>Users will appear here once they sign up.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <UserIcon className="size-4 text-muted-foreground" />
                        {u.display_name}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        items={ROLE_OPTIONS}
                        onValueChange={(newRole) => { if (newRole) roleMut.mutate({ userId: u.id, role: newRole }); }}
                        disabled={u.id === currentUser?.id}
                      >
                        <SelectTrigger className="w-28">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {ROLE_OPTIONS.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="capitalize">
                        {u.plan ?? "starter"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {u.id === currentUser?.id ? (
                        <Badge variant="secondary">You</Badge>
                      ) : (
                        <Badge variant={u.disabled ? "destructive" : "default"}>
                          {u.disabled ? "Disabled" : "Active"}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {u.id !== currentUser?.id && (
                        <Button
                          variant={u.disabled ? "outline" : "destructive"}
                          size="sm"
                          onClick={() => statusMut.mutate({ userId: u.id, disabled: !u.disabled })}
                        >
                          {u.disabled ? "Re-enable" : "Disable"}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="flex items-center justify-between pt-4">
              <p className="text-sm text-muted-foreground">
                Page {page} of {totalPages} ({total} total users)
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => { setPage((p) => p - 1); setJumpInput(""); }}
                >
                  <ChevronLeftIcon className="size-4" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground whitespace-nowrap">Go to</span>
                <Input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={jumpInput}
                  onChange={(e) => setJumpInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      const n = parseInt(jumpInput, 10);
                      if (n >= 1 && n <= totalPages) { setPage(n); setJumpInput(""); }
                    }
                  }}
                  placeholder={`1-${totalPages}`}
                  className="w-20 h-8 text-sm text-center"
                />
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => { setPage((p) => p + 1); setJumpInput(""); }}
                >
                  Next
                  <ChevronRightIcon className="size-4" />
                </Button>
              </div>
            </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
