"use client";

import { useCallback, useEffect, useState } from "react";

import { InvitesSection } from "@/components/admin/InvitesSection";
import { RegistrationsSection } from "@/components/admin/RegistrationsSection";
import { SettingsSection } from "@/components/admin/SettingsSection";
import { UsageSection } from "@/components/admin/UsageSection";
import { UsersSection } from "@/components/admin/UsersSection";
import { Badge } from "@/components/ui/Badge";
import { Tabs, panelProps, type TabItem } from "@/components/ui/Tabs";
import { pendingRegistrations } from "@/lib/admin";
import { getAppConfig } from "@/lib/config";

type AdminTab = "users" | "registrations" | "invites" | "usage" | "settings";

/**
 * Full admin dashboard (ARCHITECTURE.md §10). Sectioned via tabs: Users,
 * Registrations (only in approval mode), Invites, Usage, System settings (incl.
 * operator key). Gated to admins by the admin layout. The Registrations tab
 * carries a live pending-count badge.
 */
export default function AdminPage() {
  const [tab, setTab] = useState<AdminTab>("users");
  const [approvalMode, setApprovalMode] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const refreshPending = useCallback(async () => {
    try {
      const config = await getAppConfig();
      const isApproval = config.registration_mode === "approval";
      setApprovalMode(isApproval);
      if (isApproval) {
        const pending = await pendingRegistrations();
        setPendingCount(pending.length);
      } else {
        setPendingCount(0);
      }
    } catch {
      // Non-fatal: keep current view.
    }
  }, []);

  useEffect(() => {
    void refreshPending();
  }, [refreshPending]);

  const items: TabItem<AdminTab>[] = [
    { id: "users", label: "Users" },
    ...(approvalMode
      ? [
          {
            id: "registrations" as const,
            label: "Registrations",
            badge: pendingCount ? (
              <Badge tone="warning" className="px-1.5 py-0">
                {pendingCount}
              </Badge>
            ) : undefined,
          },
        ]
      : []),
    { id: "invites", label: "Invites" },
    { id: "usage", label: "Usage" },
    { id: "settings", label: "Settings" },
  ];

  // If approval mode flips off while the tab is selected, fall back to Users.
  useEffect(() => {
    if (!approvalMode && tab === "registrations") setTab("users");
  }, [approvalMode, tab]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage users, registrations, invites, usage, and install settings.
        </p>
      </div>

      <Tabs label="Admin sections" value={tab} onChange={setTab} items={items} />

      <div className="animate-fade-in">
        {tab === "users" ? (
          <div {...panelProps("users")}>
            <UsersSection />
          </div>
        ) : null}
        {tab === "registrations" && approvalMode ? (
          <div {...panelProps("registrations")}>
            <RegistrationsSection onChange={() => void refreshPending()} />
          </div>
        ) : null}
        {tab === "invites" ? (
          <div {...panelProps("invites")}>
            <InvitesSection />
          </div>
        ) : null}
        {tab === "usage" ? (
          <div {...panelProps("usage")}>
            <UsageSection />
          </div>
        ) : null}
        {tab === "settings" ? (
          <div {...panelProps("settings")}>
            <SettingsSection />
          </div>
        ) : null}
      </div>
    </div>
  );
}
