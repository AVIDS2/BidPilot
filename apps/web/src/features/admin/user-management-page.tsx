import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listUsers, updateUserRole, setUserStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { UsersIcon, ShieldIcon, UserIcon } from "lucide-react";

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

  const { data: users, isLoading } = useQuery({
    queryFn: listUsers,
    queryKey: ["admin-users"],
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

  return (
    <div className="mx-auto max-w-5xl py-8">
      <div className="flex items-center gap-3 mb-6">
        <UsersIcon className="size-6" />
        <h1 className="text-2xl font-bold tracking-tight">User Management</h1>
        {users && <Badge variant="secondary">{users.length} users</Badge>}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users</CardTitle>
        </CardHeader>
        <CardContent>
          {!users?.length ? (
            <p className="text-muted-foreground text-center py-8">No users found.</p>
          ) : (
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
                        onValueChange={(newRole) => { if (newRole) roleMut.mutate({ userId: u.id, role: newRole }); }}
                      >
                        <SelectTrigger className="w-28">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="member">Member</SelectItem>
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
          )}
        </CardContent>
      </Card>
    </div>
  );
}
