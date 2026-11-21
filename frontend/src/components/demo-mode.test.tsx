import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DemoNotice, DemoProvider } from "./demo-mode";
import { AuthForm } from "./auth-form";
import { UploadZone } from "./documents/upload-zone";
import { api } from "../lib/api";
import { waitForDemo } from "../lib/demo-wake";

const { replace, refresh } = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));
vi.mock("../lib/api", () => ({ api: vi.fn() }));
vi.mock("../lib/demo-wake", () => ({ waitForDemo: vi.fn().mockResolvedValue(undefined) }));
beforeEach(() => { vi.mocked(api).mockReset(); replace.mockReset(); vi.mocked(waitForDemo).mockReset().mockResolvedValue(undefined); });

it("keeps standard authentication when the demo is off", () => {
  render(<DemoProvider enabled={false}><DemoNotice /><AuthForm /></DemoProvider>);
  expect(screen.getByLabelText("Password")).toBeInTheDocument();
  expect(screen.queryByText("Read-only portfolio demo")).not.toBeInTheDocument();
});

it("enters a visitor session without requesting credentials", async () => {
  vi.mocked(api).mockResolvedValue({ status: "ok" });
  render(<DemoProvider enabled><DemoNotice /><AuthForm /></DemoProvider>);
  expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Explore the demo" }));
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  expect(api).toHaveBeenCalledWith("/demo/enter", { method: "POST" });
});

it("shows demo capacity failures without redirecting", async () => {
  vi.mocked(api).mockRejectedValue(new Error("Demo visitor capacity reached"));
  render(<DemoProvider enabled><AuthForm /></DemoProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Explore the demo" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("capacity");
  expect(replace).not.toHaveBeenCalled();
});

it("removes file selection and explains unavailable uploads", () => {
  render(<DemoProvider enabled><UploadZone organizationId="demo" limit={1024} onUploaded={vi.fn()} /></DemoProvider>);
  expect(screen.queryByLabelText("Document files")).not.toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent("Uploads are disabled");
});

it("does not submit session entry when the backend has not woken", async () => {
  vi.mocked(waitForDemo).mockRejectedValue(new Error("Please retry shortly"));
  render(<DemoProvider enabled><AuthForm /></DemoProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Explore the demo" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("retry");
  expect(api).not.toHaveBeenCalled();
});
