"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { FormError } from "@/components/FormError";
import { Input } from "@/components/Input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { getAppConfig } from "@/lib/config";
import type { RegistrationMode } from "@/lib/types";

type Phase = "form" | "pending";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<RegistrationMode | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [phase, setPhase] = useState<Phase>("form");

  // Load the operator's registration mode so the form can adapt.
  useEffect(() => {
    let active = true;
    getAppConfig()
      .then((config) => {
        if (active) setMode(config.registration_mode);
      })
      .catch(() => {
        // Fall back to the most permissive form (no invite field) on failure.
        if (active) setMode("open");
      });
    return () => {
      active = false;
    };
  }, []);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFieldErrors({});
    setFormError(null);
    setSubmitting(true);
    try {
      const res = await register({
        email,
        password,
        inviteToken: mode === "invite" ? inviteToken : undefined,
      });
      // approval mode → 202 {status:"pending"} (no token returned)
      if (res.status === "pending") {
        setPhase("pending");
        return;
      }
      // open / valid-invite → auto-logged-in by the context.
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 422 && err.field) {
          setFieldErrors({ [err.field]: err.message });
        } else if (err.status === 409) {
          setFieldErrors({ email: "An account with this email already exists." });
        } else if (err.status === 403) {
          // invite mode: invalid / consumed / missing token
          setFormError(
            mode === "invite"
              ? "This invite token is invalid or has already been used."
              : "Registration is not permitted.",
          );
        } else {
          setFormError(err.message);
        }
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (phase === "pending") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <AuthMark />
        <h1 className="text-2xl font-semibold tracking-tight text-card-foreground">
          Request received
        </h1>
        <p className="text-sm text-muted-foreground">
          Your account is pending approval by an administrator. You&apos;ll be able to sign in once
          it has been approved.
        </p>
        <Link href="/login" className="text-sm font-medium text-accent hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col items-center gap-3 text-center">
        <AuthMark />
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight text-card-foreground">
            Create your account
          </h1>
          <p className="text-sm text-muted-foreground">
            {mode === "invite"
              ? "An invite token is required to register."
              : mode === "approval"
                ? "Registrations are reviewed by an administrator."
                : "Start asking questions over your documents."}
          </p>
        </div>
      </header>

      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        <FormError message={formError} />
        <Input
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
        />
        <Input
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
          hint="At least 8 characters."
        />
        {mode === "invite" ? (
          <Input
            label="Invite token"
            type="text"
            name="invite_token"
            required
            value={inviteToken}
            onChange={(e) => setInviteToken(e.target.value)}
            error={fieldErrors.invite_token}
          />
        ) : null}
        <Button type="submit" loading={submitting} disabled={mode === null} className="mt-2 w-full">
          Create account
        </Button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}

/** Small accent-tinted brand mark shown above the auth form headings. */
function AuthMark() {
  return (
    <span
      aria-hidden="true"
      className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-accent/10 text-accent ring-1 ring-inset ring-accent/25"
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2.5l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.9L12 2.5z"
          fill="currentColor"
        />
        <path
          d="M5 19.5h14"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          opacity="0.5"
        />
      </svg>
    </span>
  );
}
