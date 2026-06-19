/**
 * Tiny, zero-dependency SAFE markdown renderer for model- and document-derived
 * text (ARCHITECTURE.md §8/§11/§14).
 *
 * Design constraints (non-negotiable, from the security model):
 *   - HTML is DISABLED. Raw HTML in the source is rendered as literal text, never
 *     parsed. There is NO `dangerouslySetInnerHTML` anywhere — we build a React
 *     element tree, so the framework escapes all text by construction.
 *   - Only an allow-list of inline/block constructs is recognized; everything
 *     else degrades to plain text.
 *   - Links are NOT auto-linked or rendered as anchors (a malicious document
 *     could otherwise inject `javascript:`/`data:` URLs or exfiltration links).
 *     A `[label](url)` is rendered as its label text only.
 *
 * Supported subset:
 *   blocks   : paragraphs, blank-line separation, fenced ``` code blocks,
 *              `#`..`###` headings, `-`/`*` and `1.` lists, `>` blockquotes
 *   inline   : **bold**, *italic* / _italic_, `inline code`
 *
 * This is intentionally small (no streaming markdown library) so it stays well
 * within the CSP/bundle budget and has an auditable surface.
 */

import { Fragment, type ReactNode } from "react";

// ---- Inline parsing ---------------------------------------------------------

/** A single inline-markup matcher. Order matters (code first, then bold). */
interface InlineRule {
  regex: RegExp;
  render: (text: string, key: string) => ReactNode;
}

const INLINE_RULES: InlineRule[] = [
  // Inline code: `…` — content is rendered verbatim (no nested inline parsing).
  {
    regex: /`([^`]+)`/,
    render: (text, key) => (
      <code
        key={key}
        className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground"
      >
        {text}
      </code>
    ),
  },
  // Bold: **…** (double markers checked before single-marker italics).
  {
    regex: /\*\*([^*]+)\*\*/,
    render: (text, key) => (
      <strong key={key} className="font-semibold">
        {parseInline(text, `${key}-b`)}
      </strong>
    ),
  },
  // Italic: *…* or _…_
  {
    regex: /\*([^*]+)\*|_([^_]+)_/,
    render: (text, key) => (
      <em key={key} className="italic">
        {parseInline(text, `${key}-i`)}
      </em>
    ),
  },
];

/**
 * Recursively parse inline markup into a React node array. Unmatched text is
 * emitted as plain (escaped-by-React) strings.
 */
function parseInline(text: string, keyBase: string): ReactNode {
  if (text === "") return null;

  let best: { rule: InlineRule; index: number; match: RegExpExecArray } | null = null;
  for (const rule of INLINE_RULES) {
    const m = rule.regex.exec(text);
    if (m && (best === null || m.index < best.index)) {
      best = { rule, index: m.index, match: m };
    }
  }

  if (best === null) {
    return text;
  }

  const { rule, index, match } = best;
  const before = text.slice(0, index);
  const inner = match[1] ?? match[2] ?? "";
  const after = text.slice(index + match[0].length);

  return (
    <Fragment key={`${keyBase}-frag`}>
      {before}
      {rule.render(inner, `${keyBase}-${index}`)}
      {parseInline(after, `${keyBase}-after`)}
    </Fragment>
  );
}

// ---- Block parsing ----------------------------------------------------------

type Block =
  | { kind: "p"; lines: string[] }
  | { kind: "heading"; level: number; text: string }
  | { kind: "code"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; lines: string[] };

function parseBlocks(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block: ``` … ``` (language hint after the fence is ignored).
    if (/^```/.test(line.trim())) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !/^```/.test(lines[i].trim())) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // skip closing fence (or run off the end)
      blocks.push({ kind: "code", text: code.join("\n") });
      continue;
    }

    // Blank line: separates blocks.
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    // Headings: #, ##, ### (max level 3 for our type scale).
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2].trim() });
      i += 1;
      continue;
    }

    // Unordered/ordered lists: consecutive `- `/`* ` or `1. ` lines.
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items: string[] = [];
      const itemRe = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-*]\s+(.*)$/;
      while (i < lines.length && itemRe.test(lines[i])) {
        const m = itemRe.exec(lines[i]);
        items.push(m ? m[1] : lines[i]);
        i += 1;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }

    // Blockquote: consecutive `>` lines.
    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      blocks.push({ kind: "quote", lines: quote });
      continue;
    }

    // Paragraph: gather consecutive non-blank, non-special lines.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !/^```/.test(lines[i].trim()) &&
      !/^(#{1,3})\s+/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i]) &&
      !/^\s*>\s?/.test(lines[i])
    ) {
      para.push(lines[i]);
      i += 1;
    }
    blocks.push({ kind: "p", lines: para });
  }

  return blocks;
}

/** Render paragraph lines, preserving soft line breaks within the paragraph. */
function renderLines(lines: string[], keyBase: string): ReactNode {
  return lines.map((line, idx) => (
    <Fragment key={`${keyBase}-l${idx}`}>
      {idx > 0 ? <br /> : null}
      {parseInline(line, `${keyBase}-l${idx}`)}
    </Fragment>
  ));
}

const HEADING_CLASS: Record<number, string> = {
  1: "mt-3 text-base font-semibold text-foreground",
  2: "mt-3 text-sm font-semibold text-foreground",
  3: "mt-2 text-sm font-medium text-foreground",
};

export interface SafeMarkdownProps {
  content: string;
  className?: string;
}

/**
 * Render `content` as safe markdown. The output is a React element tree (no HTML
 * string), so all text is escaped by React and no script/HTML can execute.
 */
export function SafeMarkdown({ content, className }: SafeMarkdownProps) {
  const blocks = parseBlocks(content);

  return (
    <div
      className={className}
      // `dir="auto"` lets the browser pick LTR/RTL per the first strong
      // character — required for mixed Persian/English answers (ARCHITECTURE §11).
      dir="auto"
    >
      {blocks.map((block, idx) => {
        const key = `b${idx}`;
        switch (block.kind) {
          case "heading": {
            // Map markdown level 1..3 onto h3..h5 (page <h1>/<h2> own the chrome).
            const Tag = `h${block.level + 2}` as "h3" | "h4" | "h5";
            return (
              <Tag key={key} className={HEADING_CLASS[block.level] ?? HEADING_CLASS[3]}>
                {parseInline(block.text, `${key}-h`)}
              </Tag>
            );
          }
          case "code":
            return (
              <pre
                key={key}
                className="my-2 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs text-foreground"
              >
                <code>{block.text}</code>
              </pre>
            );
          case "list":
            return block.ordered ? (
              <ol key={key} className="my-2 list-decimal ps-5 text-sm">
                {block.items.map((item, j) => (
                  <li key={`${key}-i${j}`} className="my-0.5">
                    {parseInline(item, `${key}-i${j}`)}
                  </li>
                ))}
              </ol>
            ) : (
              <ul key={key} className="my-2 list-disc ps-5 text-sm">
                {block.items.map((item, j) => (
                  <li key={`${key}-i${j}`} className="my-0.5">
                    {parseInline(item, `${key}-i${j}`)}
                  </li>
                ))}
              </ul>
            );
          case "quote":
            return (
              <blockquote
                key={key}
                className="my-2 border-s-2 border-border ps-3 text-sm text-muted-foreground"
              >
                {renderLines(block.lines, `${key}-q`)}
              </blockquote>
            );
          case "p":
          default:
            return (
              <p key={key} className="my-1.5 whitespace-pre-wrap text-sm leading-relaxed">
                {renderLines(block.lines, `${key}-p`)}
              </p>
            );
        }
      })}
    </div>
  );
}
