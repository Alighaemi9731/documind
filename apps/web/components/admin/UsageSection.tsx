"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { FormError } from "@/components/FormError";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Field";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Sparkline } from "@/components/ui/Sparkline";
import { getUsage, type UsagePoint } from "@/lib/admin";
import { ApiError } from "@/lib/api";

/**
 * Usage analytics: a time-series across all users (or one user), grouped by day
 * or month, rendered as hand-rolled inline SVG sparklines (no chart library,
 * §11). Totals are summarized alongside the trend.
 */
export function UsageSection() {
  const [series, setSeries] = useState<UsagePoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<"day" | "month">("day");
  const [userId, setUserId] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getUsage({ group_by: groupBy, user_id: userId.trim() || undefined });
      setSeries(res.series);
    } catch (err) {
      setSeries([]);
      setError(err instanceof ApiError ? err.message : "Could not load usage.");
    }
  }, [groupBy, userId]);

  useEffect(() => {
    const id = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(id);
  }, [load]);

  const totals = useMemo(() => {
    const list = series ?? [];
    return {
      tokensIn: list.reduce((sum, p) => sum + p.tokens_in, 0),
      tokensOut: list.reduce((sum, p) => sum + p.tokens_out, 0),
    };
  }, [series]);

  const inValues = (series ?? []).map((p) => p.tokens_in);
  const outValues = (series ?? []).map((p) => p.tokens_out);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Select
          label="Group by"
          value={groupBy}
          onChange={(e) => setGroupBy(e.target.value as "day" | "month")}
          options={[
            { value: "day", label: "Day" },
            { value: "month", label: "Month" },
          ]}
        />
        <div className="flex-1">
          <Input
            label="Filter by user id"
            placeholder="Optional user UUID"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
          />
        </div>
      </div>

      <FormError message={error} />

      {series === null ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-28 w-full rounded-2xl" />
          <Skeleton className="h-28 w-full rounded-2xl" />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <UsageCard
            title="Input tokens"
            total={totals.tokensIn}
            values={inValues}
            buckets={series.length}
          />
          <UsageCard
            title="Output tokens"
            total={totals.tokensOut}
            values={outValues}
            buckets={series.length}
          />
        </div>
      )}

      {series && series.length === 0 ? (
        <p className="text-sm text-muted-foreground">No usage recorded for this window.</p>
      ) : null}
    </div>
  );
}

function UsageCard({
  title,
  total,
  values,
  buckets,
}: {
  title: string;
  total: number;
  values: number[];
  buckets: number;
}) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-start justify-between">
        <div className="flex flex-col">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {title}
          </span>
          <span className="mt-1 text-2xl font-semibold tabular-nums">{total.toLocaleString()}</span>
        </div>
        <Sparkline
          values={values}
          width={120}
          height={36}
          label={`${title} trend over ${buckets} buckets`}
        />
      </div>
      <span className="text-xs text-muted-foreground">{buckets} buckets</span>
    </Card>
  );
}
