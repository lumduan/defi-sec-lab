import { connection } from "next/server";

import Explorer from "@/components/Explorer";
import { loadInspection } from "@/lib/inspection";

export default async function Page() {
  // Render per request: the internal API only exists at runtime, never during `next build`.
  await connection();
  const initial = await loadInspection("fork");
  return <Explorer initial={initial} />;
}
