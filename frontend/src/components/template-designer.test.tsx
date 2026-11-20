import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TemplateDesigner } from "./template-designer";

it("edits business field descriptions while preserving immutable-version context and rules", () => {
  const update = vi.fn();
  render(
    <TemplateDesigner
      value={JSON.stringify({
        name: "Contract facts",
        parent_id: "prior-version",
        fields: [
          {
            name: "fee",
            label: "Fee",
            type: "money",
            description: "",
            required: true,
          },
        ],
        rules: [
          {
            name: "High fee",
            type: "threshold",
            field: "fee",
            threshold: 40000,
            severity: "medium",
          },
        ],
        obligations: true,
      })}
      onChange={update}
    />,
  );
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Annual contractual fee" },
  });
  const saved = JSON.parse(update.mock.calls[0][0]);
  expect(saved.parent_id).toBe("prior-version");
  expect(saved.fields[0].description).toBe("Annual contractual fee");
  expect(saved.rules[0].threshold).toBe(40000);
  expect(
    screen.getByText("Advanced JSON editor").closest("details"),
  ).not.toHaveAttribute("open");
});

it("keeps malformed advanced definitions editable without crashing the form", () => {
  const update = vi.fn();
  render(
    <TemplateDesigner
      value={'{"name":"Invalid", "fields":[null]}'}
      onChange={update}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("correct the JSON");
  fireEvent.change(screen.getByLabelText("Template JSON"), {
    target: { value: '{"name":"Fixed","fields":[]}' },
  });
  expect(update).toHaveBeenCalledWith('{"name":"Fixed","fields":[]}');
});
