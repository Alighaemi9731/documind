/**
 * Tiny class-name joiner. Filters out falsy values so callers can write
 * conditional classes without pulling in a dependency.
 */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}
