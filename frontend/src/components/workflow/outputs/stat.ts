/** Safely read a numeric field from a node's free-form output payload. */
export function num(
  output: Record<string, unknown>,
  key: string,
): number | undefined {
  const value = output[key];
  return typeof value === "number" ? value : undefined;
}

/** Safely read a string field from a node's free-form output payload. */
export function str(
  output: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = output[key];
  return typeof value === "string" ? value : undefined;
}
