import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DocumentLibrary } from "./document-library";
import { api } from "../../lib/api";
import { exampleDocument } from "../../test/document-fixtures";

const { router } = vi.hoisted(() => ({ router: { replace: vi.fn() } }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../../lib/api", () => ({
  api: vi.fn(),
  ApiError: class extends Error {
    constructor(public status: number) {
      super();
    }
  },
}));
const mockApi = vi.mocked(api);
const user = { id: "alice", name: "Alice", email: "alice@example.com" };
const org = {
  id: exampleDocument.organization_id,
  name: "Research team",
  role: "admin",
};
beforeEach(() => {
  mockApi.mockReset();
  mockApi.mockImplementation(async (path) => {
    if (path === "/organizations") return [org];
    if (path.endsWith("/config")) return { upload_max_bytes: 20971520 };
    return { items: [exampleDocument], total: 1, page: 1, page_size: 20 };
  });
});

it("loads the library and sends filename, status, and format filters", async () => {
  render(<DocumentLibrary user={user} />);
  expect(await screen.findByText("Research.pdf")).toBeInTheDocument();
  expect(screen.getByText("completed")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Search documents"), {
    target: { value: "Research" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search" }));
  fireEvent.change(screen.getByLabelText("Filter by status"), {
    target: { value: "completed" },
  });
  fireEvent.change(screen.getByLabelText("Filter by file type"), {
    target: { value: "pdf" },
  });
  await waitFor(() =>
    expect(mockApi).toHaveBeenCalledWith(
      expect.stringMatching(/q=Research.*status=completed.*format=pdf/),
      expect.anything(),
    ),
  );
});

it("switches organizations without retaining the previous document list", async () => {
  mockApi.mockImplementation(async (path) => {
    if (path === "/organizations")
      return [
        org,
        {
          id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          name: "Other team",
          role: "member",
        },
      ];
    if (path.endsWith("/config")) return { upload_max_bytes: 20971520 };
    return {
      items: path.includes(org.id) ? [exampleDocument] : [],
      total: path.includes(org.id) ? 1 : 0,
      page: 1,
      page_size: 20,
    };
  });
  render(<DocumentLibrary user={user} />);
  expect(await screen.findByText("Research.pdf")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Active organization"), {
    target: { value: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb" },
  });
  expect(await screen.findByText("Your library is ready")).toBeInTheDocument();
  expect(screen.queryByText("Research.pdf")).not.toBeInTheDocument();
});

it("shows a useful empty state without organizations", async () => {
  mockApi.mockResolvedValue([]);
  render(<DocumentLibrary user={user} />);
  expect(
    await screen.findByText("Create a workspace first"),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Choose files" }),
  ).not.toBeInTheDocument();
});
