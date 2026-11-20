import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { useState } from "react";
import { AnswerText } from "./answer-text";
import { BusinessValues, Dialog, displayValue, useConfirmation } from "./ui";
import { WorkspaceShell } from "./workspace-shell";
import { preferredOrganization } from "../lib/organization-preference";

it("opens only valid application-managed inline citations and never interprets model HTML", () => {
  const open = vi.fn();
  render(
    <AnswerText
      text={"Evidence [1, 2]. Unknown [9]. <img src=x onerror=alert(1)>"}
      sourceCount={2}
      onSource={open}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Inspect source 2" }));
  expect(open).toHaveBeenCalledWith(1);
  expect(
    screen.queryByRole("button", { name: "Inspect source 9" }),
  ).not.toBeInTheDocument();
  expect(document.querySelector("img")).toBeNull();
  expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
});

it("shows business values without rounding precise monetary strings", () => {
  const value = {
    value: { currency: "USD", amount: "9007199254740999.99" },
    raw: "original source text",
  };
  render(<BusinessValues value={value} />);
  expect(screen.getByText("USD 9,007,199,254,740,999.99")).toBeInTheDocument();
  expect(screen.getByText("original source text")).toBeInTheDocument();
  expect(
    screen.getByText("Original data & provenance").closest("details"),
  ).not.toHaveAttribute("open");
  expect(displayValue(null)).toBe("Not established");
});

it("requires an explicit confirmation and allows cancellation", async () => {
  const remove = vi.fn();
  function Sample() {
    const { confirm, confirmation } = useConfirmation();
    return (
      <>
        {confirmation}
        <button
          onClick={async () => {
            if (
              await confirm("Remove record", "This action removes the record.")
            )
              remove();
          }}
        >
          Remove
        </button>
      </>
    );
  }
  render(<Sample />);
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  expect(remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(remove).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Remove" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  await vi.waitFor(() => expect(remove).toHaveBeenCalledOnce());
});

it("handles dialog Escape cancellation and restores the trigger focus", () => {
  function Sample() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button onClick={() => setOpen(true)}>Inspect</button>
        {open && (
          <Dialog title="Evidence" onClose={() => setOpen(false)}>
            Source text
          </Dialog>
        )}
      </>
    );
  }
  render(<Sample />);
  const trigger = screen.getByRole("button", { name: "Inspect" });
  trigger.focus();
  fireEvent.click(trigger);
  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { bubbles: false, cancelable: true }),
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

it("preserves organization context in navigation without treating preferences as authorization", () => {
  sessionStorage.setItem("documind.organization", "removed-membership");
  expect(
    preferredOrganization([{ id: "authorized", name: "Team", role: "member" }]),
  ).toBe("authorized");
  render(
    <WorkspaceShell
      active="assistant"
      title="Assistant"
      description="Sources"
      organizationId="authorized"
    >
      Workspace
    </WorkspaceShell>,
  );
  expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
    "href",
    "/documents?organization=authorized",
  );
  expect(screen.getByRole("link", { name: /AI Assistant/ })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

it("provides keyboard-accessible account controls using the actual user", () => {
  render(
    <WorkspaceShell
      active="overview"
      title="Overview"
      description="Workspace"
      user={{ id: "alice", name: "Alice", email: "alice@example.test" }}
    >
      Content
    </WorkspaceShell>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
  expect(
    screen.getByRole("dialog", { name: "Your account" }),
  ).toBeInTheDocument();
  expect(screen.getByText("alice@example.test")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
});
