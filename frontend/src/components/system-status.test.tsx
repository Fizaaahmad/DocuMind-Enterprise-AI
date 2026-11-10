import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchHealth } from "../lib/health";
import { SystemStatus } from "./system-status";

vi.mock("../lib/health", () => ({ fetchHealth: vi.fn() }));
const mockHealth = vi.mocked(fetchHealth);

beforeEach(() => mockHealth.mockReset());

it("renders service health and refreshes after a failure", async () => {
  mockHealth.mockResolvedValueOnce({ api: "ok", database: "unavailable", pgvector: "unavailable" });
  render(<SystemStatus />);
  expect(await screen.findByText("Some services need attention")).toBeInTheDocument();
  expect(screen.getAllByText("Unavailable")).toHaveLength(2);
  mockHealth.mockResolvedValueOnce({ api: "ok", database: "ok", pgvector: "ok" });
  fireEvent.click(screen.getByRole("button", { name: "Refresh status" }));
  await waitFor(() => expect(screen.getByText("All services operational")).toBeInTheDocument());
  expect(screen.getAllByText("Operational")).toHaveLength(3);
  expect(mockHealth).toHaveBeenCalledTimes(2);
});
