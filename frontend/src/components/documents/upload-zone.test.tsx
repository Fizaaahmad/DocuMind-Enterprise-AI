import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { UploadZone } from "./upload-zone";
import { uploadDocument } from "../../lib/documents";
import { exampleDocument } from "../../test/document-fixtures";

vi.mock("../../lib/documents", async (original) => ({
  ...(await original<typeof import("../../lib/documents")>()),
  uploadDocument: vi.fn(),
}));
const mockUpload = vi.mocked(uploadDocument);
beforeEach(() => {
  mockUpload.mockReset();
});

it("reports real transfer progress and queues an accepted document", async () => {
  let finish!: (value: typeof exampleDocument) => void;
  mockUpload.mockImplementation((_org, _file, progress) => {
    progress(50);
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  const uploaded = vi.fn();
  render(
    <UploadZone organizationId="org" limit={1024} onUploaded={uploaded} />,
  );
  fireEvent.change(screen.getByLabelText("Document files"), {
    target: {
      files: [new File(["text"], "notes.txt", { type: "text/plain" })],
    },
  });
  expect(await screen.findByRole("progressbar")).toHaveAttribute("value", "50");
  expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
  finish(exampleDocument);
  expect(await screen.findByText("Queued for processing")).toBeInTheDocument();
  expect(uploaded).toHaveBeenCalledTimes(1);
});

it("rejects unsupported and oversized files before sending them", async () => {
  render(<UploadZone organizationId="org" limit={1024} onUploaded={vi.fn()} />);
  fireEvent.change(screen.getByLabelText("Document files"), {
    target: {
      files: [
        new File(["x"], "script.exe"),
        new File(["x".repeat(2048)], "large.txt"),
      ],
    },
  });
  await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(2));
  expect(mockUpload).not.toHaveBeenCalled();
});

it("shows upload failures and supports cancellation", async () => {
  mockUpload.mockRejectedValueOnce(new Error("Storage unavailable"));
  render(<UploadZone organizationId="org" limit={1024} onUploaded={vi.fn()} />);
  const file = new File(["text"], "notes.txt");
  fireEvent.change(screen.getByLabelText("Document files"), {
    target: { files: [file] },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Storage unavailable",
  );
  mockUpload.mockImplementation(
    (_org, _file, _progress, signal) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener("abort", () =>
          reject(new DOMException("Canceled", "AbortError")),
        ),
      ),
  );
  fireEvent.change(screen.getByLabelText("Document files"), {
    target: { files: [file] },
  });
  fireEvent.click(
    await screen.findByRole("button", { name: "Cancel uploads" }),
  );
  expect(await screen.findByText("Canceled")).toBeInTheDocument();
});
