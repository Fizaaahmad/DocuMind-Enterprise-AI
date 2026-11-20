import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { WorkspaceOverview } from "./workspace-overview";

vi.mock("../lib/api", () => ({ api: vi.fn() }));
const mocked = vi.mocked(api);
beforeEach(() => {
  mocked.mockReset();
});

it("uses actual inventory and record metrics and links to the authorized document", async () => {
  mocked.mockImplementation(async (path) => {
    if (path.includes("/summary"))
      return {
        totals: {
          pending_reviews: 4,
          open_obligations: 2,
          overdue_obligations: 1,
        },
        inventory: { documents: { completed: 12, pending: 7 }, analyses: {} },
        counting: "Records may overlap",
      };
    if (path.includes("/documents?"))
      return {
        items: [
          {
            id: "doc",
            filename: "Actual.txt",
            format: "txt",
            status: "completed",
            section_count: 1,
          },
        ],
        total: 19,
      };
    return { items: [] };
  });
  render(<WorkspaceOverview organization="org" />);
  expect(await screen.findByText("19")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Actual.txt/ })).toHaveAttribute(
    "href",
    "/documents?organization=org&document=doc",
  );
  expect(
    screen.getByText(/including development mock runs/),
  ).toBeInTheDocument();
});

it("does not fabricate zero metrics when loading fails", async () => {
  mocked.mockRejectedValue(new Error("unavailable"));
  render(<WorkspaceOverview organization="org" />);
  await screen.findByRole("alert");
  expect(screen.queryByText("0", { exact: true })).not.toBeInTheDocument();
  await waitFor(() =>
    expect(screen.queryByLabelText("Loading content")).not.toBeInTheDocument(),
  );
});
