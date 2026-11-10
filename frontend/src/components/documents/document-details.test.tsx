import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DocumentDetails } from "./document-details";
import { api } from "../../lib/api";
import { exampleDocument } from "../../test/document-fixtures";

vi.mock("../../lib/api", () => ({ api: vi.fn() }));
const mockApi = vi.mocked(api);
const props = {
  initial: exampleDocument,
  organizationId: exampleDocument.organization_id,
  onClose: vi.fn(),
  onChange: vi.fn(),
};
beforeEach(() => {
  vi.clearAllMocks();
  mockApi.mockImplementation(async (path) =>
    path.includes("/content")
      ? {
          document_id: exampleDocument.id,
          total: 1,
          page: 1,
          page_size: 5,
          sections: [
            {
              id: "section",
              ordinal: 0,
              label: "Page 1",
              page_number: 1,
              text: "Extracted source text",
            },
          ],
        }
      : exampleDocument,
  );
});

it("renders source references and hides destructive controls from ordinary readers", async () => {
  render(<DocumentDetails {...props} canManage={false} />);
  expect(await screen.findByText("Extracted source text")).toBeInTheDocument();
  expect(screen.getByText("Page 1")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Delete document" }),
  ).not.toBeInTheDocument();
});

it("deletes with confirmation and refreshes the library", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<DocumentDetails {...props} canManage />);
  fireEvent.click(screen.getByRole("button", { name: "Delete document" }));
  await waitFor(() => expect(props.onClose).toHaveBeenCalled());
  expect(mockApi).toHaveBeenCalledWith(
    expect.stringContaining(exampleDocument.id),
    { method: "DELETE" },
  );
  expect(props.onChange).toHaveBeenCalled();
});

it("shows extraction errors and allows retrying failed documents", async () => {
  const failed = {
    ...exampleDocument,
    status: "failed" as const,
    error: "No readable text found",
  };
  mockApi.mockResolvedValue(failed);
  render(<DocumentDetails {...props} initial={failed} canManage />);
  expect(screen.getByRole("alert")).toHaveTextContent("No readable text found");
  fireEvent.click(screen.getByRole("button", { name: "Retry processing" }));
  await waitFor(() =>
    expect(mockApi).toHaveBeenCalledWith(expect.stringContaining("/retry"), {
      method: "POST",
    }),
  );
});
