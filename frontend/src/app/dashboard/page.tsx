import { Dashboard } from "../../components/dashboard";
import { requireUser } from "../../lib/server-auth";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const user = await requireUser();
  return <Dashboard user={user} />;
}
