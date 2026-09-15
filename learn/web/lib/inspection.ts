import "server-only";

import snapshotJson from "@/data/snapshot.json";
import type { Inspection, Loaded, Source } from "./types";

const SCHEMA = "defi-sec-lab/inspection@1";
const snapshot = snapshotJson as unknown as Inspection;
const URL_PATTERN = /\b(?:https?|wss?):\/\/\S+/gi;

function isInspection(value: unknown): value is Inspection {
  if (typeof value !== "object" || value === null) return false;
  const v = value as { schema?: unknown; stages?: unknown };
  return v.schema === SCHEMA && Array.isArray(v.stages) && v.stages.length === 4;
}

/**
 * Load an inspection from the internal API. Server-side only: the browser never learns the API address.
 * INSPECTOR_API_URL is read per request (not inlined at build). The fork view falls back to the committed
 * snapshot, so the page renders even when the backend is not running.
 */
export async function loadInspection(source: Source): Promise<Loaded> {
  const base = process.env.INSPECTOR_API_URL;
  let error = "the inspector API is not configured for this deployment";
  if (base) {
    try {
      const response = await fetch(`${base}/v1/inspection?source=${source}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(source === "live" ? 20_000 : 8_000),
      });
      const body: unknown = await response.json().catch(() => null);
      if (response.ok && isInspection(body)) return { data: body, origin: "api" };
      const detail =
        typeof body === "object" && body !== null && "detail" in body
          ? String((body as { detail: unknown }).detail)
          : `HTTP ${response.status}`;
      error = detail.replace(URL_PATTERN, "<url-redacted>"); // defense in depth: the API already strips URLs
    } catch {
      error = "the inspector API is unreachable";
    }
  }
  if (source === "fork") return { data: snapshot, origin: "snapshot", error };
  return { data: null, origin: "error", error };
}
