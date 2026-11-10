import { ApiError, apiResponse, refreshSession } from "./api";

export type DocumentStatus = "pending" | "processing" | "completed" | "failed";
export type DocumentRecord = {
  id: string;
  organization_id: string;
  uploader_id: string | null;
  filename: string;
  format: "pdf" | "docx" | "txt";
  size_bytes: number;
  checksum: string | null;
  storage_ready: boolean;
  status: DocumentStatus;
  error: string | null;
  section_count: number;
  chunk_count: number;
  character_count: number;
  chunk_size: number;
  chunk_overlap: number;
  source_metadata: Record<string, string | number>;
  created_at: string;
  processing_started_at: string | null;
  processing_completed_at: string | null;
};
export type DocumentList = {
  items: DocumentRecord[];
  total: number;
  page: number;
  page_size: number;
};
export type DocumentContent = {
  document_id: string;
  total: number;
  page: number;
  page_size: number;
  sections: {
    id: string;
    ordinal: number;
    page_number: number | null;
    label: string;
    text: string;
  }[];
};

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return bytes < 1024 * 1024
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

async function csrfToken(): Promise<string> {
  const response = await fetch("/api/backend/auth/csrf", {
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok)
    throw new ApiError(
      response.status,
      "Unable to secure upload. Please try again.",
    );
  return (await response.json()).csrf_token;
}

export async function uploadDocument(
  org: string,
  file: File,
  onProgress: (percent: number) => void,
  signal: AbortSignal,
): Promise<DocumentRecord> {
  await refreshSession();
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await csrfToken();
    if (signal.aborted) throw new DOMException("Upload canceled", "AbortError");
    try {
      return await new Promise<DocumentRecord>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        const abort = () => xhr.abort();
        const clean = () => signal.removeEventListener("abort", abort);
        xhr.open("POST", `/api/backend/organizations/${org}/documents`);
        xhr.withCredentials = true;
        xhr.timeout = 120000;
        xhr.setRequestHeader("X-CSRF-Token", token);
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable)
            onProgress(Math.round((event.loaded / event.total) * 100));
        };
        xhr.onload = () => {
          clean();
          let body;
          try {
            body = JSON.parse(xhr.responseText);
          } catch {
            reject(new ApiError(xhr.status, "Invalid upload response"));
            return;
          }
          if (xhr.status >= 200 && xhr.status < 300) resolve(body);
          else
            reject(
              new ApiError(
                xhr.status,
                typeof body.detail === "string"
                  ? body.detail
                  : "Upload could not be accepted",
              ),
            );
        };
        xhr.onerror = () => {
          clean();
          reject(
            new ApiError(
              0,
              "Upload connection failed. Check the library before retrying.",
            ),
          );
        };
        xhr.ontimeout = () => {
          clean();
          reject(
            new ApiError(
              0,
              "Upload timed out. Check the library before retrying.",
            ),
          );
        };
        xhr.onabort = () => {
          clean();
          reject(new DOMException("Upload canceled", "AbortError"));
        };
        signal.addEventListener("abort", abort, { once: true });
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401 && attempt === 0) {
        await refreshSession();
        continue;
      }
      throw error;
    }
  }
  throw new ApiError(401, "Please sign in again");
}

export async function downloadDocument(org: string, document: DocumentRecord) {
  const response = await apiResponse(
    `/organizations/${org}/documents/${document.id}/download`,
  );
  const url = URL.createObjectURL(await response.blob());
  const link = window.document.createElement("a");
  link.href = url;
  link.download = document.filename;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
