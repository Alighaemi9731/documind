"use client";

import { cn } from "@/lib/cn";

export interface TabItem<T extends string = string> {
  id: T;
  label: React.ReactNode;
  /** Optional count/badge rendered after the label. */
  badge?: React.ReactNode;
}

export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (id: T) => void;
  /** Accessible label for the tablist. */
  label: string;
  className?: string;
}

/**
 * Accessible underline tablist (roving via arrow keys). Panels are owned by the
 * caller; pass `aria-controls`/`id` via the rendered panel using `panelId(id)`.
 */
export function Tabs<T extends string>({ items, value, onChange, label, className }: TabsProps<T>) {
  function onKeyDown(e: React.KeyboardEvent) {
    const idx = items.findIndex((it) => it.id === value);
    if (idx < 0) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const dir = e.key === "ArrowRight" ? 1 : -1;
      const next = (idx + dir + items.length) % items.length;
      onChange(items[next].id);
    }
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn("flex gap-1 overflow-x-auto border-b border-border", className)}
    >
      {items.map((it) => {
        const active = it.id === value;
        return (
          <button
            key={it.id}
            type="button"
            role="tab"
            id={`tab-${it.id}`}
            aria-selected={active}
            aria-controls={`panel-${it.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(it.id)}
            className={cn(
              "-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              active
                ? "border-accent text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {it.label}
            {it.badge}
          </button>
        );
      })}
    </div>
  );
}

/** Props to spread onto a tab panel paired with {@link Tabs}. */
export function panelProps(id: string) {
  return { role: "tabpanel", id: `panel-${id}`, "aria-labelledby": `tab-${id}` } as const;
}
