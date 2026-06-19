"use client";

/**
 * React auth context backed by the in-memory access token and the API client.
 *
 * On mount it attempts a single-flight silent refresh (a page reload loses the
 * in-memory access token but the httpOnly refresh cookie survives), then loads
 * the current user from GET /api/auth/me. Components consume {user, login,
 * register, logout, isLoading, refreshUser} via useAuth().
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  apiFetch,
  apiLogout,
  apiPublicFetch,
  refreshAccessToken,
  setAccessToken,
} from "./api";
import type { CurrentUser, LoginResponse, RegisterResponse } from "./types";

interface RegisterInput {
  email: string;
  password: string;
  inviteToken?: string;
}

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Returns the raw register response so callers can branch on mode. */
  register: (input: RegisterInput) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(): Promise<CurrentUser | null> {
  try {
    return await apiFetch<CurrentUser>("/auth/me");
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
      return null;
    }
    throw err;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    setUser(await fetchMe());
  }, []);

  // Bootstrap: try a silent refresh, then load the current user.
  useEffect(() => {
    let active = true;
    (async () => {
      const refreshed = await refreshAccessToken();
      if (!active) return;
      if (refreshed) {
        const me = await fetchMe();
        if (active) setUser(me);
      }
      if (active) setIsLoading(false);
    })().catch(() => {
      if (active) setIsLoading(false);
    });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiPublicFetch<LoginResponse>("/auth/login", {
      method: "POST",
      json: { email, password },
    });
    setAccessToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (input: RegisterInput): Promise<RegisterResponse> => {
    const body: Record<string, string> = {
      email: input.email,
      password: input.password,
    };
    if (input.inviteToken) {
      body.invite_token = input.inviteToken;
    }
    const res = await apiPublicFetch<RegisterResponse>("/auth/register", {
      method: "POST",
      json: body,
    });
    // open mode → auto-login (201 carries an access token + user)
    if (res.access_token && res.user) {
      setAccessToken(res.access_token);
      setUser(res.user);
    }
    return res;
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, login, register, logout, refreshUser }),
    [user, isLoading, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
