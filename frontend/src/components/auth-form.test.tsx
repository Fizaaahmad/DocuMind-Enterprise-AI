import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthForm } from "./auth-form";
import { api, ApiError } from "../lib/api";

const { replace, refresh } = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, refresh }) }));
vi.mock("../lib/api", () => ({
  api: vi.fn(),
  ApiError: class extends Error {
    constructor(
      public status: number,
      message: string,
    ) {
      super(message);
    }
  },
}));
const mockApi = vi.mocked(api);
beforeEach(() => {
  mockApi.mockReset();
  replace.mockReset();
  refresh.mockReset();
});

function fill() {
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "alice@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "correct horse battery staple" },
  });
}

it("signs in and navigates to the server-guarded dashboard", async () => {
  mockApi.mockResolvedValue({ id: "user" });
  render(<AuthForm />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  expect(mockApi).toHaveBeenCalledWith(
    "/auth/login",
    expect.objectContaining({ method: "POST" }),
  );
  expect(refresh).toHaveBeenCalled();
});

it("validates signup fields and disables duplicate submission while pending", async () => {
  let resolve!: (value: unknown) => void;
  mockApi.mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  render(<AuthForm signup />);
  expect(screen.getByLabelText("Password")).toHaveAttribute("minlength", "12");
  fireEvent.change(screen.getByLabelText("Full name"), {
    target: { value: "Alice" },
  });
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(screen.getByRole("button", { name: "Please wait…" })).toBeDisabled();
  expect(mockApi).toHaveBeenCalledTimes(1);
  resolve({ id: "user" });
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
});

it("shows an accessible login error without navigating", async () => {
  mockApi.mockRejectedValue(new ApiError(401, "Invalid email or password"));
  render(<AuthForm />);
  fill();
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid email or password",
  );
  expect(replace).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
});
