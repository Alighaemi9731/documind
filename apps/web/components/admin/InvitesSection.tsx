"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { FormError } from "@/components/FormError";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Table, type Column } from "@/components/ui/Table";
import { useToast } from "@/components/ui/Toast";
import {
  createInvite,
  deleteInvite,
  type Invite,
  type InviteCreated,
  inviteUrl,
  listInvites,
} from "@/lib/admin";
import { ApiError } from "@/lib/api";
import type { UserRole } from "@/lib/types";

/**
 * Invites: create → the token/link is shown ONCE in a modal (copy-the-URL
 * delivery, ADR-0001/0016; there is no SMTP). The list shows metadata only —
 * never the token — and supports revoke.
 */
export function InvitesSection() {
  const toast = useToast();
  const [invites, setInvites] = useState<Invite[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("user");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<InviteCreated | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setInvites(await listInvites());
    } catch (err) {
      setInvites([]);
      setError(err instanceof ApiError ? err.message : "Could not load invites.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const result = await createInvite({ email: email.trim() || undefined, role });
      setCreated(result);
      setEmail("");
      setRole("user");
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create the invite.");
    } finally {
      setCreating(false);
    }
  }

  async function onRevoke(invite: Invite) {
    try {
      await deleteInvite(invite.id);
      setInvites((prev) => (prev ? prev.filter((i) => i.id !== invite.id) : prev));
      toast.success("Invite revoked.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not revoke the invite.");
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard.");
    } catch {
      toast.error("Copy failed — select and copy manually.");
    }
  }

  const columns = useMemo<Column<Invite>[]>(
    () => [
      {
        key: "email",
        header: "Email",
        cell: (i) => i.email ?? <span className="text-muted-foreground">Any</span>,
      },
      { key: "role", header: "Role", cell: (i) => <Badge>{i.role}</Badge> },
      {
        key: "status",
        header: "Status",
        cell: (i) =>
          i.consumed_at ? (
            <Badge tone="neutral">used</Badge>
          ) : new Date(i.expires_at).getTime() < Date.now() ? (
            <Badge tone="warning">expired</Badge>
          ) : (
            <Badge tone="success" dot>
              active
            </Badge>
          ),
      },
      {
        key: "expires",
        header: "Expires",
        cell: (i) => (
          <span className="text-muted-foreground">
            {new Date(i.expires_at).toLocaleDateString()}
          </span>
        ),
      },
      {
        key: "actions",
        header: "Actions",
        align: "end",
        cell: (i) =>
          i.consumed_at ? null : (
            <Button size="sm" variant="ghost" onClick={() => void onRevoke(i)}>
              Revoke
            </Button>
          ),
      },
    ],
    // onRevoke is stable enough for this list; intentionally minimal deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  return (
    <div className="flex flex-col gap-5">
      <Card className="p-5">
        <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={onCreate}>
          <div className="flex-1">
            <Input
              label="Email (optional)"
              type="email"
              placeholder="anyone@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              hint="Leave blank for an open invite token."
            />
          </div>
          <Select
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            options={[
              { value: "user", label: "User" },
              { value: "admin", label: "Admin" },
            ]}
          />
          <Button type="submit" loading={creating}>
            Create invite
          </Button>
        </form>
      </Card>

      <FormError message={error} />

      {invites === null ? (
        <Skeleton className="h-40 w-full rounded-2xl" />
      ) : (
        <Table
          caption="Invites"
          columns={columns}
          rows={invites}
          rowKey={(i) => i.id}
          empty={
            <div className="rounded-2xl border border-dashed border-border bg-card px-6 py-12 text-center text-sm text-muted-foreground">
              No invites yet.
            </div>
          }
        />
      )}

      <Modal
        open={created !== null}
        onClose={() => setCreated(null)}
        title="Invite created"
        description="Copy this link now — the token is shown only once."
        footer={<Button onClick={() => setCreated(null)}>Done</Button>}
      >
        {created ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Invite link
              </span>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate rounded-lg border border-border bg-muted px-3 py-2 font-mono text-xs">
                  {inviteUrl(created.token)}
                </code>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => void copy(inviteUrl(created.token))}
                >
                  Copy
                </Button>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Role: {created.role} · expires {new Date(created.expires_at).toLocaleString()}
            </p>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
