/**
 * Back-compat re-export. The canonical Input (RTL-aware, token-driven) now lives
 * in components/ui/Field. Existing call sites keep working.
 */
export { Input } from "./ui/Field";
export type { InputProps } from "./ui/Field";
