# Self-hosted fonts

This directory holds self-hosted font subsets referenced by `@font-face` in
`app/globals.css`. They are served same-origin so the strict CSP (`font-src
'self'`) holds and there is **no Google Fonts dependency** (ARCHITECTURE.md §4 /
§11 / §14).

## Vazirmatn (Persian/Arabic)

Expected file: **`Vazirmatn-subset.woff2`** — a variable-weight (100–900) subset
of [Vazirmatn](https://github.com/rastikerdar/vazirmatn) (SIL OFL 1.1) covering
the Arabic/Persian Unicode ranges declared by the `@font-face` `unicode-range`.

The integrator generates the subset in CI (it is intentionally **not** committed
as a binary). Example using `fonttools`:

```bash
pyftsubset Vazirmatn[wght].ttf \
  --output-file=public/fonts/Vazirmatn-subset.woff2 \
  --flavor=woff2 \
  --layout-features='*' \
  --unicodes='U+0600-06FF,U+0750-077F,U+08A0-08FF,U+200C-200D,U+FB50-FDFF,U+FE70-FEFF'
```

Until the subset is present the UI gracefully falls back to the SF/system stack
for Persian glyphs — nothing breaks, the text just renders in the system font.
The OFL license text for the bundled subset must ship alongside it.
