import { NextResponse, type NextRequest } from "next/server";

import { loadInspection } from "@/lib/inspection";

// The browser's only door to fresh data: it proxies to the internal API server-side and validates the input.
export async function GET(request: NextRequest) {
  const source = request.nextUrl.searchParams.get("source");
  if (source !== "fork" && source !== "live") {
    return NextResponse.json({ error: "source must be 'fork' or 'live'" }, { status: 400 });
  }
  const loaded = await loadInspection(source);
  return NextResponse.json(loaded, {
    status: loaded.data ? 200 : 502,
    headers: { "Cache-Control": "no-store" },
  });
}
