import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Assistant } from "./assistant";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: vi.fn() }));
const mockApi = vi.mocked(api);
const source = {
  source_id: "chunk",
  document_id: "doc",
  filename: "Policy.txt",
  label: "Section 1",
  page_number: null,
  text: "Annual leave is twenty days.",
  similarity: 0.9,
};
let failure = false;
let gpt = false;

beforeEach(() => {
  failure = false;
  gpt = false;
  mockApi.mockReset();
  mockApi.mockImplementation(async (path, options) => {
    if (path === "/organizations")
      return [{ id: "org", name: "Research", role: "admin" }];
    if (path.endsWith("/status"))
      return {
        embeddings_enabled: true,
        provider: gpt ? "openai" : "mock",
        is_mock: !gpt,
        documents: [
          {
            id: "doc",
            filename: "Policy.txt",
            status: "completed",
            index_status: "completed",
          },
        ],
      };
    if (path.endsWith("/search")) {
      if (failure) throw new Error("Local embedding model unavailable");
      return { sources: [source] };
    }
    if (path.endsWith("/conversations"))
      return options?.method === "POST" ? { id: "chat", title: "New" } : [];
    if (path.endsWith("/messages"))
      return options?.method === "POST"
        ? {}
        : [
            {
              id: "message",
              question: "Leave?",
              answer: "Annual leave is twenty days. [1]",
              state: "completed",
              is_mock: !gpt,
              provider: gpt ? "openai" : "mock",
              usage: gpt
                ? {
                    model: "offline-model",
                    input_tokens: 100,
                    output_tokens: 20,
                    estimated_cost_usd: "0.001",
                  }
                : null,
              citations: [{ ...source, quote: source.text }],
            },
          ];
    return {};
  });
});

describe("Assistant", () => {
  it("labels genuine-provider answers separately from mock output and shows usage", async () => {
    gpt = true;
    render(<Assistant />);
    await screen.findByRole("button", { name: "Ask assistant" });
    fireEvent.change(screen.getByLabelText("Ask your documents"), {
      target: { value: "Leave?" },
    });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Ask assistant" }),
      ).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Ask assistant" }));
    expect(
      await screen.findByText(/OpenAI GPT · verify source evidence/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/offline-model · Input 100 \/ output 20 tokens/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Development mock — extractive preview/),
    ).not.toBeInTheDocument();
  });
  it("labels mock responses and opens exact search passages", async () => {
    render(<Assistant />);
    await screen.findByText(/Development mock — extractive preview/);
    fireEvent.change(screen.getByLabelText("Ask your documents"), {
      target: { value: "Leave?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Semantic search" }));
    const hit = await screen.findByRole("button", {
      name: /Policy.txt · Section 1/,
    });
    fireEvent.click(hit);
    expect(screen.getByLabelText("Source passage")).toHaveTextContent(
      "Annual leave is twenty days.",
    );
    expect(mockApi).toHaveBeenCalledWith(
      "/organizations/org/intelligence/search",
      expect.objectContaining({
        body: JSON.stringify({ question: "Leave?", document_ids: [] }),
      }),
    );
  });

  it("sends selected documents and displays mock conversation citations", async () => {
    render(<Assistant />);
    await screen.findByText(/Development mock — extractive preview/);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByLabelText("Ask your documents"), {
      target: { value: "Leave?" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Preview mock answer" }),
    );
    await screen.findByRole("button", { name: "Inspect source 1" });
    expect(
      screen.getByText(/Annual leave is twenty days\./),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Development mock · extractive preview/),
    ).toBeInTheDocument();
    expect(mockApi).toHaveBeenCalledWith(
      "/organizations/org/intelligence/conversations/chat/messages",
      expect.objectContaining({
        body: JSON.stringify({ question: "Leave?", document_ids: ["doc"] }),
      }),
    );
  });

  it("shows failures and restores controls", async () => {
    failure = true;
    render(<Assistant />);
    await screen.findByText(/Development mock — extractive preview/);
    fireEvent.change(screen.getByLabelText("Ask your documents"), {
      target: { value: "Leave?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Semantic search" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Local embedding model unavailable",
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Semantic search" }),
      ).toBeEnabled(),
    );
  });
});
