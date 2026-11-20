import { DocumentLibrary } from "../../components/documents/document-library";
import { requireUser } from "../../lib/server-auth";

export const metadata = { title: "Document library" };

export const dynamic = "force-dynamic";

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<{ organization?: string; document?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;
  return (
    <DocumentLibrary
      user={user}
      initialOrganization={params.organization}
      initialDocument={params.document}
    />
  );
}
