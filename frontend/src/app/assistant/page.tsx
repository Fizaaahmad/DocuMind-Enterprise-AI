import { Assistant } from "../../components/assistant";
import { requireUser } from "../../lib/server-auth";

export const dynamic = "force-dynamic";

export default async function AssistantPage() {
  await requireUser();
  return <Assistant />;
}
