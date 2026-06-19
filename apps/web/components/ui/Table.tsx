"use client";

import { cn } from "@/lib/cn";

export interface Column<Row> {
  /** Stable key. */
  key: string;
  header: React.ReactNode;
  /** Cell renderer. */
  cell: (row: Row) => React.ReactNode;
  /** Hide this column on narrow screens (still shown in the stacked card). */
  className?: string;
  /** Right/end-align numeric columns. */
  align?: "start" | "end";
}

export interface TableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  /** Accessible caption / label for the table. */
  caption?: string;
  /** Rendered when there are no rows. */
  empty?: React.ReactNode;
}

/**
 * Responsive data table: a real <table> at >=sm, and a stacked card list on
 * narrow screens (each cell labelled by its column header). Keeps semantics +
 * a11y while staying readable on mobile (ARCHITECTURE.md §11 Table → cards).
 */
export function Table<Row>({ columns, rows, rowKey, caption, empty }: TableProps<Row>) {
  if (rows.length === 0 && empty !== undefined) {
    return <>{empty}</>;
  }

  return (
    <div>
      {/* Wide: a semantic table. */}
      <div className="hidden overflow-hidden rounded-2xl border border-border sm:block">
        <table className="w-full text-sm">
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          <thead>
            <tr className="border-b border-border bg-muted/40 text-start">
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={cn(
                    "px-4 py-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground",
                    col.align === "end" ? "text-end" : "text-start",
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={rowKey(row)}
                className="border-b border-border last:border-0 transition-colors hover:bg-muted/30"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3 align-middle",
                      col.align === "end" ? "text-end" : "text-start",
                    )}
                  >
                    {col.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Narrow: stacked cards. */}
      <ul className="flex flex-col gap-3 sm:hidden">
        {rows.map((row) => (
          <li
            key={rowKey(row)}
            className="rounded-2xl border border-border bg-card p-4 text-sm shadow-sm"
          >
            <dl className="flex flex-col gap-2">
              {columns.map((col) => (
                <div key={col.key} className="flex items-start justify-between gap-3">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {col.header}
                  </dt>
                  <dd className="text-end">{col.cell(row)}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
