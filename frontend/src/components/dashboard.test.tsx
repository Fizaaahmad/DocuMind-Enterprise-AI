import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { Dashboard } from "./dashboard";
import { api } from "../lib/api";

const { replace, router } = vi.hoisted(() => {
  const replace = vi.fn();
  return { replace, router: { replace, refresh: vi.fn() } };
});
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("../lib/api", () => ({
  api: vi.fn(),
  ApiError: class extends Error {
    constructor(public status: number) {
      super();
    }
  },
}));
const mockApi = vi.mocked(api);
const user = { id: "alice", name: "Alice", email: "alice@example.com" };
beforeEach(() => {
  mockApi.mockReset();
  replace.mockReset();
});

it("renders member access without administrative controls", async () => {
  mockApi.mockImplementation(async (path) =>
    path === "/organizations"
      ? [{ id: "org", name: "Research", role: "member" }]
      : [
          {
            user_id: "alice",
            name: "Alice",
            email: user.email,
            role: "member",
          },
        ],
  );
  render(<Dashboard user={user} />);
  expect(
    await screen.findByText(
      "You can view this team. Only organization Admins can manage membership.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Add member" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Remove" }),
  ).not.toBeInTheDocument();
});

it("switches organizations without mixing member lists", async () => {
  mockApi.mockImplementation(async (path) => {
    if (path === "/organizations")
      return [
        { id: "one", name: "First", role: "admin" },
        { id: "two", name: "Second", role: "member" },
      ];
    return path.includes("/one/")
      ? [
          {
            user_id: "bob",
            name: "Bob",
            email: "bob@example.com",
            role: "member",
          },
        ]
      : [
          {
            user_id: "carol",
            name: "Carol",
            email: "carol@example.com",
            role: "admin",
          },
        ];
  });
  render(<Dashboard user={user} />);
  expect(await screen.findByText("Bob")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Active organization"), {
    target: { value: "two" },
  });
  expect(await screen.findByText("Carol")).toBeInTheDocument();
  expect(screen.queryByText("Bob")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Add member" }),
  ).not.toBeInTheDocument();
});

it("creates an organization and displays admin membership controls", async () => {
  let created = false;
  mockApi.mockImplementation(async (path, init) => {
    if (path === "/organizations" && init?.method === "POST") {
      created = true;
      return { id: "new", name: "New team", role: "admin" };
    }
    if (path === "/organizations")
      return created ? [{ id: "new", name: "New team", role: "admin" }] : [];
    return [];
  });
  render(<Dashboard user={user} />);
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Create organization" }),
    ).toBeEnabled(),
  );
  fireEvent.change(screen.getByLabelText("Organization name"), {
    target: { value: "New team" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create organization" }));
  expect(
    await screen.findByRole("button", { name: "Add member" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Organization created. You are its Admin."),
  ).toBeInTheDocument();
});

it("clears an organization after the current user removes their own membership", async () => {
  let removed = false;
  vi.spyOn(window, "confirm").mockReturnValue(true);
  mockApi.mockImplementation(async (path, init) => {
    if (init?.method === "DELETE") { removed = true; return undefined; }
    if (path === "/organizations") return removed ? [] : [{ id: "org", name: "Research", role: "admin" }];
    return [{ user_id: user.id, name: user.name, email: user.email, role: "admin" }];
  });
  render(<Dashboard user={user} />);
  fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
  await waitFor(() => expect(screen.queryByLabelText("Active organization")).not.toBeInTheDocument());
  expect(screen.getByText("Member removed.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
