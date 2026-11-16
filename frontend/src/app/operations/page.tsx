import { OperationsWorkspace } from "../../components/operations-workspace";
import { requireUser } from "../../lib/server-auth";

export const dynamic = "force-dynamic";

export default async function OperationsPage() {
  await requireUser();
  return <OperationsWorkspace />;
}
