import { StructuredWorkspace } from "../../components/structured-workspace";
import { requireUser } from "../../lib/server-auth";

export const dynamic = "force-dynamic";

export default async function IntelligencePage() {
  await requireUser();
  return <StructuredWorkspace />;
}
