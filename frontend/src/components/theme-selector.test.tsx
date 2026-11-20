import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ThemeSelector } from "./theme-selector";

let dark = false;
let changed: () => void;
beforeEach(() => {
  dark = false;
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      get matches() {
        return dark;
      },
      addEventListener: vi.fn((_event, callback) => {
        changed = callback;
      }),
      removeEventListener: vi.fn(),
    })),
  );
  localStorage.clear();
});
afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  delete document.documentElement.dataset.preference;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
it("persists a manual selection and restores it after remount", () => {
  const view = render(<ThemeSelector />);
  fireEvent.change(screen.getByLabelText("Color theme"), {
    target: { value: "dark" },
  });
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("documind.theme")).toBe("dark");
  view.unmount();
  render(<ThemeSelector />);
  expect(screen.getByLabelText("Color theme")).toHaveValue("dark");
});
it("follows system changes only while System is selected", () => {
  render(<ThemeSelector />);
  dark = true;
  act(() => changed());
  expect(document.documentElement.dataset.theme).toBe("dark");
  fireEvent.change(screen.getByLabelText("Color theme"), {
    target: { value: "light" },
  });
  act(() => changed());
  expect(document.documentElement.dataset.theme).toBe("light");
});
it("synchronizes another tab and handles unavailable storage", () => {
  render(<ThemeSelector />);
  localStorage.setItem("documind.theme", "dark");
  act(() =>
    window.dispatchEvent(
      new StorageEvent("storage", { key: "documind.theme" }),
    ),
  );
  expect(screen.getByLabelText("Color theme")).toHaveValue("dark");
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("Unavailable");
  });
  fireEvent.change(screen.getByLabelText("Color theme"), {
    target: { value: "light" },
  });
  expect(document.documentElement.dataset.theme).toBe("light");
});
