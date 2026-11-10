import { DocumentLibrary } from "../../components/documents/document-library";
import { requireUser } from "../../lib/server-auth";

export const dynamic = "force-dynamic";

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<{ organization?: string }>;
}) {
  const user = await requireUser();
  return (
    <DocumentLibrary
      user={user}
      initialOrganization={(await searchParams).organization}
    />
  );
}
