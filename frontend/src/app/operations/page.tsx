import { OperationsWorkspace } from "../../components/operations-workspace";
import { requireUser } from "../../lib/server-auth";

export const metadata = { title: "Enterprise Operations" };

export const dynamic = "force-dynamic";

export default async function OperationsPage({
  searchParams,
}: {
  searchParams: Promise<{ view?: string; focus?: string; engine?: string }>;
}) {
  const user = await requireUser("/operations");
  const params = await searchParams;
  return (
    <OperationsWorkspace
      user={user}
      initialView={params.view}
      initialFocus={params.focus}
      initialEngine={params.engine}
    />
  );
}
