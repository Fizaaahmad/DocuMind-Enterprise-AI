import { StructuredWorkspace } from "../../components/structured-workspace";
import { requireUser } from "../../lib/server-auth";

export const metadata = { title: "Document Intelligence" };

export const dynamic = "force-dynamic";

export default async function IntelligencePage({
  searchParams,
}: {
  searchParams: Promise<{ organization?: string; run?: string; item?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  return (
    <StructuredWorkspace
      user={user}
      initialOrganization={params.organization}
      initialRun={params.run}
      initialItem={params.item}
    />
  );
}
