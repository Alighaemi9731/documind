/**
 * HeroArt — a hand-authored, original inline SVG that tells the DocuMind story
 * at a glance: a stack of source documents on the start side flows along a
 * glowing "answer beam" into a single grounded, cited answer card on the end
 * side, set against a faint constellation of retrieval nodes.
 *
 * Design notes
 *  - THEME-AWARE: every stroke/fill is driven by `currentColor` (inherits the
 *    foreground) or the `--accent` token, so it adapts to light/dark AND to the
 *    operator's runtime branding accent without a rebuild (ARCHITECTURE.md §11).
 *  - DECORATIVE: purely illustrative, so the whole figure is aria-hidden and
 *    carries no semantic text.
 *  - ZERO JS: this is a server component. The subtle motion is pure CSS
 *    (defined in globals.css) and is disabled under prefers-reduced-motion, so
 *    it never enters the landing's initial JS chunk.
 *  - RTL: the SVG is mirrored as a whole via a `scale(-1,1)` group when the
 *    document direction is RTL, so "source → answer" still reads start→end.
 */

export function HeroArt({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 520 440"
      role="presentation"
      aria-hidden="true"
      focusable="false"
      className={className}
      // Scope the gradient/filter ids; multiple instances stay valid.
      data-heroart
    >
      <defs>
        {/* Accent → transparent wash used for the glow + beam. */}
        <linearGradient id="ha-beam" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="hsl(var(--accent))" stopOpacity="0" />
          <stop offset="0.5" stopColor="hsl(var(--accent))" stopOpacity="0.9" />
          <stop offset="1" stopColor="hsl(var(--accent))" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="ha-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="hsl(var(--accent))" stopOpacity="0.55" />
          <stop offset="1" stopColor="hsl(var(--accent))" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ha-card" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="hsl(var(--card))" stopOpacity="1" />
          <stop offset="1" stopColor="hsl(var(--card))" stopOpacity="0.86" />
        </linearGradient>
        <linearGradient id="ha-answer" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="hsl(var(--accent))" stopOpacity="0.16" />
          <stop offset="1" stopColor="hsl(var(--accent))" stopOpacity="0.04" />
        </linearGradient>
      </defs>

      {/* Soft aurora bloom behind the answer card. */}
      <ellipse cx="372" cy="208" rx="168" ry="150" fill="url(#ha-glow)" />

      {/* Constellation: faint retrieval nodes + links (drawn first, behind). */}
      <g
        stroke="hsl(var(--accent))"
        strokeOpacity="0.30"
        strokeWidth="1.25"
        fill="hsl(var(--accent))"
      >
        <line x1="150" y1="120" x2="250" y2="90" strokeOpacity="0.18" />
        <line x1="250" y1="90" x2="356" y2="120" strokeOpacity="0.18" />
        <line x1="150" y1="120" x2="120" y2="232" strokeOpacity="0.14" />
        <line x1="356" y1="320" x2="250" y2="356" strokeOpacity="0.16" />
        <line x1="250" y1="356" x2="146" y2="320" strokeOpacity="0.16" />
        <g className="ha-twinkle" fillOpacity="0.85">
          <circle cx="250" cy="90" r="3" />
          <circle cx="150" cy="120" r="2.5" />
          <circle cx="356" cy="120" r="2.5" />
          <circle cx="120" cy="232" r="2" />
          <circle cx="356" cy="320" r="2.5" />
          <circle cx="250" cy="356" r="3" />
          <circle cx="146" cy="320" r="2" />
        </g>
      </g>

      {/* The travelling "answer beam": a faint rail with a bright pulse riding it. */}
      <g>
        <path
          d="M150 244 C 230 244, 250 208, 332 208"
          fill="none"
          stroke="hsl(var(--accent))"
          strokeOpacity="0.22"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          className="ha-beam-pulse"
          d="M150 244 C 230 244, 250 208, 332 208"
          fill="none"
          stroke="url(#ha-beam)"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeDasharray="46 220"
        />
      </g>

      {/* ---- Source document stack (start side) ---- */}
      <g className="ha-float-slow">
        {/* back sheets */}
        <g transform="rotate(-9 116 250)">
          <rect
            x="58"
            y="196"
            width="116"
            height="148"
            rx="14"
            fill="url(#ha-card)"
            stroke="currentColor"
            strokeOpacity="0.14"
            strokeWidth="1.5"
          />
        </g>
        <g transform="rotate(-4 124 248)">
          <rect
            x="66"
            y="190"
            width="116"
            height="148"
            rx="14"
            fill="url(#ha-card)"
            stroke="currentColor"
            strokeOpacity="0.18"
            strokeWidth="1.5"
          />
        </g>
        {/* front sheet with text lines + a dog-eared corner */}
        <g>
          <rect
            x="74"
            y="184"
            width="116"
            height="148"
            rx="14"
            fill="hsl(var(--card))"
            stroke="currentColor"
            strokeOpacity="0.28"
            strokeWidth="1.5"
          />
          {/* folded corner accent */}
          <path d="M168 184 h22 v22 z" fill="hsl(var(--accent))" fillOpacity="0.14" />
          <g stroke="currentColor" strokeOpacity="0.34" strokeWidth="3.5" strokeLinecap="round">
            <line x1="90" y1="212" x2="150" y2="212" />
            <line x1="90" y1="230" x2="166" y2="230" />
            <line x1="90" y1="248" x2="142" y2="248" />
            <line x1="90" y1="266" x2="160" y2="266" />
            <line x1="90" y1="284" x2="126" y2="284" />
          </g>
          {/* highlighted source span (the retrieved chunk) */}
          <rect
            x="88"
            y="294"
            width="78"
            height="14"
            rx="5"
            fill="hsl(var(--accent))"
            fillOpacity="0.22"
          />
        </g>
      </g>

      {/* ---- Grounded answer card (end side) ---- */}
      <g className="ha-float">
        <rect
          x="300"
          y="118"
          width="186"
          height="184"
          rx="20"
          fill="url(#ha-answer)"
          stroke="hsl(var(--accent))"
          strokeOpacity="0.45"
          strokeWidth="1.75"
        />
        <rect
          x="300"
          y="118"
          width="186"
          height="184"
          rx="20"
          fill="hsl(var(--card))"
          fillOpacity="0.55"
        />
        {/* sparkle / answer mark */}
        <g transform="translate(322 144)">
          <path
            className="ha-spark"
            d="M9 0 L11.4 6.6 L18 9 L11.4 11.4 L9 18 L6.6 11.4 L0 9 L6.6 6.6 Z"
            fill="hsl(var(--accent))"
          />
        </g>
        <rect
          x="352"
          y="146"
          width="92"
          height="10"
          rx="5"
          fill="currentColor"
          fillOpacity="0.30"
        />
        {/* answer body lines */}
        <g stroke="currentColor" strokeOpacity="0.26" strokeWidth="4" strokeLinecap="round">
          <line x1="322" y1="190" x2="462" y2="190" />
          <line x1="322" y1="208" x2="450" y2="208" />
          <line x1="322" y1="226" x2="438" y2="226" />
        </g>
        {/* citation chips — the proof the answer is grounded */}
        <g>
          <rect
            x="322"
            y="250"
            width="46"
            height="22"
            rx="11"
            fill="hsl(var(--accent))"
            fillOpacity="0.16"
            stroke="hsl(var(--accent))"
            strokeOpacity="0.5"
            strokeWidth="1.25"
          />
          <text
            x="345"
            y="265"
            textAnchor="middle"
            fontSize="11"
            fontWeight="600"
            fill="hsl(var(--accent))"
          >
            [1]
          </text>
          <rect
            x="376"
            y="250"
            width="46"
            height="22"
            rx="11"
            fill="hsl(var(--accent))"
            fillOpacity="0.16"
            stroke="hsl(var(--accent))"
            strokeOpacity="0.5"
            strokeWidth="1.25"
          />
          <text
            x="399"
            y="265"
            textAnchor="middle"
            fontSize="11"
            fontWeight="600"
            fill="hsl(var(--accent))"
          >
            [2]
          </text>
        </g>
      </g>
    </svg>
  );
}
