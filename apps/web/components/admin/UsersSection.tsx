"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { FormError } from "@/components/FormError";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Table, type Column } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  type AdminUser,
  disableUser,
  demoteUser,
  deleteUser,
  listUsers,
  promoteUser,
} from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { direction } from "@/lib/direction";
import type { UserRole, UserStatus } from "@/lib/types";

import { UserKeysModal } from "./UserKeysModal";
import { UserQuotaModal } from "./UserQuotaModal";

type Action = "promote" | "demote" | "disable" | "delete";

const STATUS_TONE: Record<UserStatus, "success" | "warning" | "danger"> = {
  active: "success",
  pending: "warning",
  disabled: "danger",
};

export function UsersSection() {
  const toast = useToast();
  const { user: me } = useAuth();
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<UserStatus | "">("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "">("");
  const [total, setTotal] = useState(0);

  const [confirm, setConfirm] = useState<{ user: AdminUser; action: Action } | null>(null);
  const [busy, setBusy] = useState(false);
  const [quotaUser, setQuotaUser] = useState<AdminUser | null>(null);
  const [keysUser, setKeysUser] = useState<AdminUser | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const res = await listUsers({
        q: query || undefined,
        status: statusFilter || undefined,
        role: roleFilter || undefined,
      });
      setUsers(res.users);
      setTotal(res.total);
    } catch (err) {
      setUsers([]);
      setLoadError(err instanceof ApiError ? err.message : "Could not load users.");
    }
  }, [query, statusFilter, roleFilter]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(id);
  }, [load]);

  async function runAction() {
    if (!confirm) return;
    setBusy(true);
    const { user, action } = confirm;
    try {
      if (action === "promote") await promoteUser(user.id);
      else if (action === "demote") await demoteUser(user.id);
      else if (action === "disable") await disableUser(user.id);
      else if (action === "delete") await deleteUser(user.id);
      toast.success(`${ACTION_LABEL[action]} ${user.email}.`);
      setConfirm(null);
      await load();
    } catch (err) {
      // Surface the last-admin guard (409) and any other failure as a toast.
      if (err instanceof ApiError && err.code === "last_admin") {
        toast.error("That is the last active admin and cannot be changed.");
      } else {
        toast.error(err instanceof ApiError ? err.message : "Action failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  const columns = useMemo<Column<AdminUser>[]>(
    () => [
      {
        key: "email",
        header: "Email",
        cell: (u) => (
          <span className="font-medium" dir={direction(u.email)}>
            {u.email}
            {me?.id === u.id ? (
              <span className="ms-2 text-xs font-normal text-muted-foreground">(you)</span>
            ) : null}
          </span>
        ),
      },
      {
        key: "role",
        header: "Role",
        cell: (u) => <Badge tone={u.role === "admin" ? "accent" : "neutral"}>{u.role}</Badge>,
      },
      {
        key: "status",
        header: "Status",
        cell: (u) => (
          <Badge tone={STATUS_TONE[u.status]} dot pulse={u.status === "pending"}>
            {u.status}
          </Badge>
        ),
      },
      {
        key: "actions",
        header: "Actions",
        align: "end",
        cell: (u) => (
          <div className="flex flex-wrap items-center justify-end gap-1.5">
            {u.role === "user" ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirm({ user: u, action: "promote" })}
              >
                Promote
              </Button>
            ) : (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirm({ user: u, action: "demote" })}
              >
                Demote
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setQuotaUser(u)}>
              Quota
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setKeysUser(u)}>
              Keys
            </Button>
            {u.status !== "disabled" ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setConfirm({ user: u, action: "disable" })}
              >
                Disable
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="danger"
              onClick={() => setConfirm({ user: u, action: "delete" })}
            >
              Delete
            </Button>
          </div>
        ),
      },
    ],
    [me?.id],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Input
            label="Search"
            hideLabel
            placeholder="Search by email…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoDir
          />
        </div>
        <Select
          label="Status"
          hideLabel
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as UserStatus | "")}
          options={[
            { value: "", label: "All statuses" },
            { value: "active", label: "Active" },
            { value: "pending", label: "Pending" },
            { value: "disabled", label: "Disabled" },
          ]}
        />
        <Select
          label="Role"
          hideLabel
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as UserRole | "")}
          options={[
            { value: "", label: "All roles" },
            { value: "admin", label: "Admin" },
            { value: "user", label: "User" },
          ]}
        />
      </div>

      {loadError ? <FormError message={loadError} /> : null}

      {users === null ? (
        <Skeleton className="h-48 w-full rounded-2xl" />
      ) : (
        <>
          <Table
            caption="Users"
            columns={columns}
            rows={users}
            rowKey={(u) => u.id}
            empty={
              <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center text-sm text-muted-foreground">
                No users match your filters.
              </div>
            }
          />
          {users.length > 0 ? (
            <p className="text-xs text-muted-foreground">
              {users.length} shown of {total}
            </p>
          ) : null}
        </>
      )}

      <Modal
        open={confirm !== null}
        onClose={() => (busy ? undefined : setConfirm(null))}
        dismissOnBackdrop={!busy}
        title={confirm ? `${ACTION_LABEL[confirm.action]} user` : ""}
        description={confirm ? CONFIRM_COPY[confirm.action](confirm.user.email) : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)} disabled={busy}>
              Cancel
            </Button>
            <Button
              variant={confirm?.action === "promote" ? "primary" : "danger"}
              loading={busy}
              onClick={() => void runAction()}
            >
              {confirm ? ACTION_LABEL[confirm.action] : "Confirm"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted-foreground">This action takes effect immediately.</p>
      </Modal>

      {quotaUser ? <UserQuotaModal user={quotaUser} onClose={() => setQuotaUser(null)} /> : null}
      {keysUser ? <UserKeysModal user={keysUser} onClose={() => setKeysUser(null)} /> : null}
    </div>
  );
}

const ACTION_LABEL: Record<Action, string> = {
  promote: "Promote",
  demote: "Demote",
  disable: "Disable",
  delete: "Delete",
};

const CONFIRM_COPY: Record<Action, (email: string) => string> = {
  promote: (e) => `Grant ${e} full admin access?`,
  demote: (e) => `Remove admin access from ${e}?`,
  disable: (e) => `Disable ${e}? They will be signed out immediately.`,
  delete: (e) => `Permanently delete ${e} and ALL of their data? This cannot be undone.`,
};
