"use client";

import { useCallback, useEffect, useState } from "react";

import { FormError } from "@/components/FormError";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { type AdminSettings, getAdminSettings, updateAdminSettings } from "@/lib/admin";
import { ApiError } from "@/lib/api";
import { applyAccent, normalizeAccent, safeLogoUrl } from "@/lib/branding";
import type { RegistrationMode } from "@/lib/types";

import { OperatorKeySection } from "./OperatorKeySection";

/**
 * Install-wide system settings (ARCHITECTURE.md §10/§11): registration mode,
 * default provider, default quota, and branding (app_name/accent/logo). The
 * accent is previewed live via the CSSOM (never an inline style attribute) and
 * persisted on save. `app_name` is plain text; `logo_url` must be same-origin.
 */
export function SettingsSection() {
  const toast = useToast();
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [registrationMode, setRegistrationMode] = useState<RegistrationMode>("open");
  const [defaultProvider, setDefaultProvider] = useState("google");
  const [defaultQuota, setDefaultQuota] = useState("");
  const [appName, setAppName] = useState("");
  const [accent, setAccent] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [accentError, setAccentError] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const s = await getAdminSettings();
      setSettings(s);
      setRegistrationMode(s.registration_mode);
      setDefaultProvider(s.default_provider);
      setDefaultQuota(s.default_quota != null ? String(s.default_quota) : "");
      setAppName(s.branding.app_name ?? "");
      setAccent(s.branding.accent_color ?? "");
      setLogoUrl(s.branding.logo_url ?? "");
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Could not load settings.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function previewAccent(value: string) {
    setAccent(value);
    if (value.trim() === "" || normalizeAccent(value)) {
      setAccentError(null);
      applyAccent(value.trim() || null);
    } else {
      setAccentError("Use a hex color (#2563eb) or HSL channels (221 83% 53%).");
    }
  }

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (accent.trim() && !normalizeAccent(accent)) {
      setAccentError("Invalid accent color.");
      return;
    }
    if (logoUrl.trim() && !safeLogoUrl(logoUrl)) {
      setLogoError("Logo must be a same-origin path starting with /.");
      return;
    }
    setLogoError(null);
    setSaving(true);
    try {
      const quotaNum =
        defaultQuota.trim() === "" ? null : Math.max(0, Math.floor(Number(defaultQuota)));
      const updated = await updateAdminSettings({
        registration_mode: registrationMode,
        default_provider: defaultProvider,
        default_quota: quotaNum,
        branding: {
          app_name: appName.trim() || "DocuMind",
          accent_color: accent.trim(),
          logo_url: safeLogoUrl(logoUrl),
        },
      });
      setSettings(updated);
      applyAccent(updated.branding.accent_color || null);
      toast.success("Settings saved.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (loadError && settings === null) {
    return (
      <Card className="flex flex-col items-start gap-3 p-6">
        <FormError message={loadError} />
        <Button variant="secondary" onClick={() => void load()}>
          Retry
        </Button>
      </Card>
    );
  }

  if (settings === null) {
    return <Skeleton className="h-72 w-full rounded-2xl" />;
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSave}>
        <Card className="flex flex-col gap-5 p-6">
          <h3 className="text-base font-semibold">Registration & defaults</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Select
              label="Registration mode"
              value={registrationMode}
              onChange={(e) => setRegistrationMode(e.target.value as RegistrationMode)}
              options={[
                { value: "open", label: "Open — anyone can sign up" },
                { value: "approval", label: "Approval — admin reviews each signup" },
                { value: "invite", label: "Invite — token required" },
              ]}
            />
            <Select
              label="Default provider"
              value={defaultProvider}
              onChange={(e) => setDefaultProvider(e.target.value)}
              options={[
                { value: "google", label: "Google (Gemini)" },
                { value: "openai", label: "OpenAI" },
                { value: "anthropic", label: "Anthropic" },
                { value: "groq", label: "Groq" },
              ]}
            />
            <Input
              label="Default monthly token quota"
              type="number"
              inputMode="numeric"
              min={0}
              value={defaultQuota}
              onChange={(e) => setDefaultQuota(e.target.value)}
              hint="Applied to new users on the shared key. Blank = unlimited."
            />
          </div>

          <div className="h-px bg-border" aria-hidden="true" />

          <h3 className="text-base font-semibold">Branding</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="App name"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              autoDir
              hint="Shown in the nav, landing, and page title."
            />
            <Input
              label="Accent color"
              value={accent}
              onChange={(e) => previewAccent(e.target.value)}
              error={accentError}
              placeholder="#2563eb or 221 83% 53%"
              hint={accentError ? undefined : "Previewed live as you type."}
            />
            <Input
              label="Logo URL"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              error={logoError}
              placeholder="/branding/logo.svg"
              hint={logoError ? undefined : "Same-origin path only."}
            />
          </div>

          <div className="flex items-center justify-end">
            <Button type="submit" loading={saving}>
              Save settings
            </Button>
          </div>
        </Card>
      </form>

      <OperatorKeySection />
    </div>
  );
}
