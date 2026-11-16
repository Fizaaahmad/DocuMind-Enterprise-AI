import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { OperationsWorkspace } from "./operations-workspace";

vi.mock("../lib/api", () => ({ api: vi.fn(), apiResponse: vi.fn() }));
const mocked = vi.mocked(api);
let canManage = true;
let conflict = false;
const row = {
  id: "item",
  run_id: "run",
  name: "Commitment candidate",
  kind: "obligation",
  original: {
    commitment: "Acme shall deliver reports",
    deadline: "2026-12-01",
  },
  corrected: null,
  evidence: [
    {
      section_id: "section",
      revision_id: "revision",
      label: "Section 1",
      start: 0,
      end: 31,
      quote: "Acme shall deliver reports",
    },
  ],
  validation: "candidate",
  effective_validation: "candidate",
  review_status: "pending",
  obligation_status: "open",
  version: 1,
  document_id: "doc",
  filename: "Contract.txt",
  template_name: "Contract facts",
  engine: "deterministic",
  contract_deadline: "2026-12-01",
  assignment_due_date: null,
  assignee_id: null,
  assignee_name: null,
  is_current: true,
  is_done: false,
  can_assign: true,
  can_review: true,
};

beforeEach(() => {
  canManage = true;
  conflict = false;
  mocked.mockReset();
  mocked.mockImplementation(async (path) => {
    if (path === "/organizations")
      return [
        { id: "org", name: "Research", role: "admin" },
        { id: "other", name: "Finance", role: "member" },
      ];
    if (path.includes("/documents?page_size"))
      return { items: [{ id: "doc", filename: "Contract.txt" }] };
    if (path.includes("/summary?"))
      return {
        totals: { records: 1, obligations: 1, open_obligations: 1 },
        severity: {},
        inventory: { documents: { completed: 1 }, analyses: { completed: 1 } },
        date_basis: "UTC",
        filters: { as_of: "2026-11-16" },
      };
    if (path.endsWith("/members"))
      return [
        { id: "alice", name: "Alice" },
        { id: "bob", name: "Bob" },
      ];
    if (path.includes("/activity?")) return { items: [], total: 0 };
    if (path.endsWith("/assignment")) {
      if (conflict) throw new Error("Result changed; reload before assigning");
      return { version: 2 };
    }
    if (path.includes("/items?"))
      return {
        items: path.includes("/other/")
          ? []
          : [{ ...row, can_assign: canManage, can_review: canManage }],
        total: path.includes("/other/") ? 0 : 1,
      };
    if (path.endsWith("/review")) return {};
    return {};
  });
});

it("shows record semantics and keeps contract and workflow dates separate", async () => {
  render(<OperationsWorkspace />);
  await screen.findByText("Commitment candidate");
  expect(
    screen.getByText(
      /independent templates may describe overlapping business items/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Contract deadline" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("columnheader", { name: "Assignment due date" }),
  ).toBeInTheDocument();
  expect(screen.getByText("2026-12-01")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Inspect / review" }));
  expect(
    await screen.findByLabelText("Workflow due date (not contract deadline)"),
  ).toHaveValue("");
});

it("drills into a metric without dropping active filters", async () => {
  render(<OperationsWorkspace />);
  await screen.findByText("Commitment candidate");
  fireEvent.change(screen.getByLabelText("Record scope"), {
    target: { value: "superseded" },
  });
  await waitFor(() =>
    expect(mocked).toHaveBeenCalledWith(
      expect.stringContaining("scope=superseded"),
    ),
  );
  fireEvent.click(
    screen.getByText("Open obligation records").closest("button")!,
  );
  await waitFor(() =>
    expect(mocked).toHaveBeenCalledWith(
      expect.stringMatching(/scope=superseded.*focus=open_obligations/),
    ),
  );
});

it("searches document choices without leaving records in a loading state", async () => {
  render(<OperationsWorkspace />);
  await screen.findByText("Commitment candidate");
  fireEvent.change(screen.getByLabelText("Find document by filename"), { target: { value: "Invoice" } });
  await waitFor(() => expect(mocked).toHaveBeenCalledWith(
    expect.stringContaining("/documents?page_size=50&q=Invoice"), expect.any(Object),
  ));
  expect(screen.getByRole("button", { name: "Export filtered CSV" })).toBeEnabled();
});

it("sends assignment versions and displays conflicts", async () => {
  conflict = true;
  render(<OperationsWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Inspect / review" }),
  );
  fireEvent.change(await screen.findByLabelText("Assign to member"), {
    target: { value: "bob" },
  });
  fireEvent.change(
    screen.getByLabelText("Workflow due date (not contract deadline)"),
    { target: { value: "2026-11-25" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save assignment" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Result changed");
  expect(mocked).toHaveBeenCalledWith(
    "/organizations/org/operations/items/item/assignment",
    expect.objectContaining({
      method: "PATCH",
      body: JSON.stringify({
        version: 1,
        assignee_id: "bob",
        due_date: "2026-11-25",
      }),
    }),
  );
});

it("hides write controls for read-only members", async () => {
  canManage = false;
  render(<OperationsWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Inspect / review" }),
  );
  expect(await screen.findByLabelText("Record inspection")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Save assignment" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Save review" }),
  ).not.toBeInTheDocument();
});

it("clears inspected evidence when switching organizations", async () => {
  render(<OperationsWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Inspect / review" }),
  );
  fireEvent.click(await screen.findByRole("button", { name: /Section 1/ }));
  expect(screen.getByLabelText("Source evidence")).toHaveTextContent(
    "Acme shall deliver reports",
  );
  fireEvent.change(screen.getByLabelText("Organization"), {
    target: { value: "other" },
  });
  await waitFor(() =>
    expect(mocked).toHaveBeenCalledWith(
      expect.stringContaining("/organizations/other/operations/items"),
    ),
  );
  expect(screen.queryByLabelText("Source evidence")).not.toBeInTheDocument();
});
