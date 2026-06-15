/**
 * Cross-linking between chat citations and the Report tab's source cards.
 *
 * Each source card carries a stable DOM id derived from its URL
 * ({@link sourceAnchorId}); a citation chip scrolls to and briefly highlights
 * that card ({@link scrollToSource}). Matching on URL keeps chat's prompt-pack
 * index decoupled from the report's source ordering.
 */

/** A stable, DOM-id-safe anchor derived from a source URL. */
export function sourceAnchorId(url: string): string {
  let hash = 0;
  for (let i = 0; i < url.length; i += 1) {
    hash = (hash * 31 + url.charCodeAt(i)) | 0;
  }
  return `src-${(hash >>> 0).toString(36)}`;
}

/** Scroll the matching source card into view and flash a highlight ring. */
export function scrollToSource(url: string): void {
  if (typeof document === "undefined") return;
  const el = document.getElementById(sourceAnchorId(url));
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("ring-2", "ring-ring", "ring-offset-2");
  window.setTimeout(() => {
    el.classList.remove("ring-2", "ring-ring", "ring-offset-2");
  }, 1600);
}
