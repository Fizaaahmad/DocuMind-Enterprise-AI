import { Assistant } from "../../components/assistant";
import { requireUser } from "../../lib/server-auth";

export const metadata = { title: "Knowledge Assistant" };

export const dynamic = "force-dynamic";

export default async function AssistantPage() {
  const user = await requireUser("/assistant");
  return <Assistant user={user} />;
}
