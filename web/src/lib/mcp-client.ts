/**
 * Client-side fetch wrapper for calling Next.js API routes.
 */

export async function fetchAnalysis(
  endpoint: string,
  body: Record<string, unknown>
) {
  const res = await fetch(`/api/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}
