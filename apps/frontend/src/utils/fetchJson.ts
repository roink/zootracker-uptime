type FetchLike = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>;

export async function fetchJson(
  input: RequestInfo | URL,
  init?: RequestInit,
  fetcher: FetchLike = fetch
) {
  const res = await fetcher(input, init);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as unknown;
}

export const isJsonObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

export function readJsonArray<T>(payload: unknown): T[] {
  if (isJsonObject(payload) && 'items' in payload) {
    const items = (payload as { items?: unknown }).items;
    if (Array.isArray(items)) {
      return items as T[];
    }
  }
  if (Array.isArray(payload)) {
    return payload as T[];
  }
  return [];
}

