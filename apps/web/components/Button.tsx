/**
 * Back-compat re-export. The canonical Button now lives in components/ui and is
 * token-driven (ARCHITECTURE.md §11). Existing call sites keep working.
 */
export { Button } from "./ui/Button";
export type { ButtonProps } from "./ui/Button";
