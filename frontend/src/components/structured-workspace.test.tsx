import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { StructuredWorkspace } from "./structured-workspace";

vi.mock("../lib/api", () => ({ api: vi.fn(), apiResponse: vi.fn() }));
const mocked = vi.mocked(api);
let manage = true;
let failure = false;
const run = {
  id: "run123",
  mode: "extract",
  engine: "deterministic",
  state: "completed",
  coverage: { complete: true },
};
const item = {
  id: "item",
  run_id: "run123",
  name: "party",
  kind: "field",
  version: 1,
  original: { value: "Acme Ltd" },
  validation: "valid",
  review_status: "pending",
  evidence: [
    {
      section_id: "section",
      revision_id: "revision",
      quote: "Party: Acme Ltd",
      label: "Section 1",
      start: 0,
      end: 15,
    },
  ],
};

beforeEach(() => {
  run.engine = "deterministic";
  manage = true;
  failure = false;
  mocked.mockReset();
  mocked.mockImplementation(async (path, options) => {
    if (path === "/organizations")
      return [
        { id: "org", name: "Research", role: manage ? "admin" : "member" },
        { id: "other", name: "Finance", role: "member" },
      ];
    if (path.includes("/documents?page_size"))
      return {
        items: [{ id: "doc", filename: "Contract.txt", status: "completed" }],
      };
    if (path.endsWith("/templates"))
      return options?.method === "POST"
        ? {}
        : [{ id: "template", name: "Contract facts", definition: {} }];
    if (path.endsWith("/revisions")) return [];
    if (path.includes("/sections?"))
      return {
        items: [
          {
            id: "coverage-section",
            label: "Section 1",
            text: "Party: Acme Ltd",
            page_number: null,
          },
        ],
        total: 1,
      };
    if (path.endsWith("/runs")) return options?.method === "POST" ? run : [run];
    if (path.endsWith("/review")) {
      if (failure) throw new Error("Result changed; reload before reviewing");
      return {};
    }
    if (path.endsWith("/runs/run123"))
      return {
        usage: run.engine === "openai" ? { model: "offline-model", input_tokens: 100, output_tokens: 20, estimated_cost_usd: "0.001" } : null,
        run,
        items: [item],
        reviews: [],
        can_manage: manage,
        superseded: false,
        sources: [{ revision_id: "revision", filename: "Contract.txt" }],
      };
    return {};
  });
});

it("labels GPT results for human review and displays measured usage", async () => {
  run.engine = "openai";
  render(<StructuredWorkspace />);
  fireEvent.click(await screen.findByRole("button", { name: /Extraction · run123/ }));
  expect(await screen.findByText(/OpenAI GPT — review candidates/)).toBeInTheDocument();
  expect(screen.getByText(/offline-model · Input 100 \/ output 20 tokens/)).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /OpenAI GPT · human review required/ })).toBeInTheDocument();
});

it("shows deterministic provenance and exact evidence", async () => {
  render(<StructuredWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Extraction · run123/ }),
  );
  expect(await screen.findByText("party")).toBeInTheDocument();
  expect(
    screen.getByText(/Deterministic \/ rule-based · completed/),
  ).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: /Contract.txt · Section 1/ }),
  );
  expect(screen.getByLabelText("Source evidence")).toHaveTextContent(
    "Party: Acme Ltd",
  );
});

it("submits optimistic review version and displays conflicts", async () => {
  failure = true;
  render(<StructuredWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Extraction · run123/ }),
  );
  fireEvent.change(await screen.findByLabelText("Review reason"), {
    target: { value: "Checked original" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save review" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Result changed");
  expect(mocked).toHaveBeenCalledWith(
    "/organizations/org/structured/runs/run123/items/item/review",
    expect.objectContaining({ body: expect.stringContaining('"version":1') }),
  );
});

it("hides management actions from read-only members", async () => {
  manage = false;
  render(<StructuredWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Extraction · run123/ }),
  );
  await screen.findByText("party");
  expect(
    screen.queryByRole("button", { name: "Save review" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Configure templates/ }),
  ).not.toBeInTheDocument();
});

it("clears source evidence and selected analysis when switching organizations", async () => {
  render(<StructuredWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Extraction · run123/ }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: /Contract.txt · Section 1/ }),
  );
  fireEvent.change(screen.getByLabelText("Organization"), {
    target: { value: "other" },
  });
  await waitFor(() =>
    expect(mocked).toHaveBeenCalledWith("/organizations/other/structured/runs"),
  );
  expect(screen.queryByLabelText("Source evidence")).not.toBeInTheDocument();
  expect(screen.queryByText("party")).not.toBeInTheDocument();
});

it("uses an inspected coverage passage to support a correction", async () => {
  render(<StructuredWorkspace />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Extraction · run123/ }),
  );
  await screen.findByText("party");
  fireEvent.click(
    screen.getByText(/Inspect revision coverage & original sections/),
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Contract.txt · revisi/ }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: /Use selected text/ }),
  );
  fireEvent.change(screen.getByLabelText(/Review action/), {
    target: { value: "correct" },
  });
  fireEvent.change(screen.getByLabelText("Corrected value"), {
    target: { value: "Acme" },
  });
  fireEvent.change(screen.getByLabelText("Correction evidence"), {
    target: { value: "coverage" },
  });
  fireEvent.change(screen.getByLabelText("Review reason"), {
    target: { value: "Checked coverage" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save review" }));
  await waitFor(() =>
    expect(mocked).toHaveBeenCalledWith(
      "/organizations/org/structured/runs/run123/items/item/review",
      expect.objectContaining({
        body: expect.stringContaining('"section_id":"coverage-section"'),
      }),
    ),
  );
});
