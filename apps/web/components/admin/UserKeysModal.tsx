"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { type AdminUser, getUserKeys, type KeyMetadata } from "@/lib/admin";
import { ApiError } from "@/lib/api";

/**
 * Per-user BYOK key oversight — FINGERPRINTS ONLY (ARCHITECTURE.md §10/§14). The
 * API never returns ciphertext or plaintext; this modal renders only the
 * provider, fingerprint, and validity. There is intentionally no way to reveal a
 * secret here.
 */
export function UserKeysModal({ user, onClose }: { user: AdminUser; onClose: () => void }) {
  const [keys, setKeys] = useState<KeyMetadata[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await getUserKeys(user.id);
        if (active) setKeys(data);
      } catch (err) {
        if (active) {
          setKeys([]);
          setError(err instanceof ApiError ? err.message : "Could not load keys.");
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [user.id]);

  return (
    <Modal
      open
      onClose={onClose}
      title="Provider keys"
      description={`${user.email} · fingerprints only, never secrets`}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {keys === null ? (
        <div className="flex flex-col gap-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : error ? (
        <p className="text-sm text-danger">{error}</p>
      ) : keys.length === 0 ? (
        <p className="text-sm text-muted-foreground">This user has no BYOK keys.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {keys.map((k) => (
            <li
              key={k.provider}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-muted/40 px-3 py-2"
            >
              <div className="flex flex-col">
                <span className="text-sm font-medium capitalize">{k.provider}</span>
                <span className="font-mono text-xs text-muted-foreground">{k.fingerprint}</span>
              </div>
              <Badge tone={k.valid ? "success" : "warning"} dot>
                {k.valid ? "valid" : "unverified"}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
