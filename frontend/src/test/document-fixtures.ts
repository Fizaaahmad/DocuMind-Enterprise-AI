import type { DocumentRecord } from "../lib/documents";

export const exampleDocument: DocumentRecord = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  uploader_id: "alice",
  filename: "Research.pdf",
  format: "pdf",
  size_bytes: 4096,
  checksum: "test-checksum",
  storage_ready: true,
  status: "completed",
  error: null,
  section_count: 1,
  chunk_count: 2,
  character_count: 1500,
  chunk_size: 1200,
  chunk_overlap: 200,
  source_metadata: { page_count: 1 },
  created_at: "2026-11-10T00:00:00Z",
  processing_started_at: "2026-11-10T00:00:01Z",
  processing_completed_at: "2026-11-10T00:00:02Z",
};
