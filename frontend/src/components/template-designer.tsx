"use client";

import { Icon } from "./ui";

type Field = {
  name: string;
  label: string;
  type: string;
  description?: string;
  required?: boolean;
};
type Rule = {
  name: string;
  type: string;
  severity?: string;
  term?: string;
  field?: string;
  threshold?: number | null;
};
type Definition = {
  name: string;
  fields?: Field[];
  rules?: Rule[];
  obligations?: boolean;
  [key: string]: unknown;
};

export function TemplateDesigner({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  let definition: Definition | null = null;
  try {
    const parsed = JSON.parse(value);
    const record = (item: unknown): item is Record<string, unknown> =>
      Boolean(item) && typeof item === "object" && !Array.isArray(item);
    const validFields =
      parsed?.fields === undefined ||
      (Array.isArray(parsed.fields) &&
        parsed.fields.every(
          (field: unknown) =>
            record(field) &&
            typeof field.name === "string" &&
            typeof field.label === "string" &&
            typeof field.type === "string",
        ));
    const validRules =
      parsed?.rules === undefined ||
      (Array.isArray(parsed.rules) &&
        parsed.rules.every(
          (rule: unknown) =>
            record(rule) &&
            typeof rule.name === "string" &&
            typeof rule.type === "string",
        ));
    if (record(parsed) && validFields && validRules)
      definition = parsed as Definition;
  } catch {
    /* The advanced editor can temporarily contain incomplete JSON. */
  }
  const data = definition;
  function patch(changes: Partial<Definition>) {
    if (data) onChange(JSON.stringify({ ...data, ...changes }, null, 2));
  }
  const fields = Array.isArray(data?.fields) ? data.fields : [];
  const rules = Array.isArray(data?.rules) ? data.rules : [];
  return (
    <div className="template-designer">
      {data ? (
        <>
          <label className="field-label">
            Template name
            <input
              className="input"
              value={data.name ?? ""}
              maxLength={100}
              onChange={(e) => patch({ name: e.target.value })}
            />
          </label>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Information to extract</h3>
            <button
              type="button"
              className="btn-secondary"
              disabled={fields.length >= 40}
              onClick={() =>
                patch({
                  fields: [
                    ...fields,
                    {
                      name: `field_${fields.length + 1}`,
                      label: "",
                      type: "text",
                      description: "",
                      required: false,
                    },
                  ],
                })
              }
            >
              <Icon name="plus" />
              Add field
            </button>
          </div>
          {fields.map((field, index) => (
            <fieldset key={index} className="template-field">
              <legend>Field {index + 1}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <label>
                  Display label
                  <input
                    className="input"
                    value={field.label ?? ""}
                    maxLength={100}
                    onChange={(e) =>
                      patch({
                        fields: fields.map((f, i) =>
                          i === index ? { ...f, label: e.target.value } : f,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Value type
                  <select
                    className="input"
                    value={field.type}
                    onChange={(e) =>
                      patch({
                        fields: fields.map((f, i) =>
                          i === index ? { ...f, type: e.target.value } : f,
                        ),
                      })
                    }
                  >
                    {[
                      "text",
                      "money",
                      "date",
                      "decimal",
                      "boolean",
                      "list",
                    ].map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Field key
                  <input
                    className="input"
                    value={field.name}
                    onChange={(e) =>
                      patch({
                        fields: fields.map((f, i) =>
                          i === index ? { ...f, name: e.target.value } : f,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Description
                  <input
                    className="input"
                    value={field.description ?? ""}
                    maxLength={500}
                    placeholder="What should the reviewer look for?"
                    onChange={(e) =>
                      patch({
                        fields: fields.map((f, i) =>
                          i === index
                            ? { ...f, description: e.target.value }
                            : f,
                        ),
                      })
                    }
                  />
                </label>
              </div>
              <div className="mt-3 flex items-center justify-between gap-3">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(field.required)}
                    onChange={(e) =>
                      patch({
                        fields: fields.map((f, i) =>
                          i === index
                            ? { ...f, required: e.target.checked }
                            : f,
                        ),
                      })
                    }
                  />
                  Required information
                </label>
                <button
                  type="button"
                  className="text-xs text-rose-700"
                  onClick={() =>
                    patch({ fields: fields.filter((_, i) => i !== index) })
                  }
                >
                  Remove field {index + 1}
                </button>
              </div>
            </fieldset>
          ))}
          <p className="text-xs text-slate-500">
            Field keys use lowercase letters, numbers and underscores.
            Deterministic extraction matches “Display label: value”; GPT uses
            descriptions and context.
          </p>
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Review rules</h3>
            <button
              type="button"
              className="btn-secondary"
              disabled={rules.length >= 40}
              onClick={() =>
                patch({
                  rules: [
                    ...rules,
                    {
                      name: "New review rule",
                      type: "contains",
                      term: "",
                      severity: "medium",
                    },
                  ],
                })
              }
            >
              <Icon name="plus" />
              Add rule
            </button>
          </div>
          {rules.map((rule, index) => (
            <fieldset key={index} className="template-field">
              <legend>Rule {index + 1}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                <label>
                  Finding name
                  <input
                    className="input"
                    value={rule.name}
                    maxLength={100}
                    onChange={(e) =>
                      patch({
                        rules: rules.map((r, i) =>
                          i === index ? { ...r, name: e.target.value } : r,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Rule condition
                  <select
                    className="input"
                    value={rule.type}
                    onChange={(e) =>
                      patch({
                        rules: rules.map((r, i) =>
                          i === index ? { ...r, type: e.target.value } : r,
                        ),
                      })
                    }
                  >
                    <option value="contains">Contains a term</option>
                    <option value="missing">Term not detected</option>
                    <option value="threshold">Value above threshold</option>
                    <option value="inconsistent">Inconsistent values</option>
                  </select>
                </label>
                {["contains", "missing"].includes(rule.type) ? (
                  <label>
                    Term to check
                    <input
                      className="input"
                      value={rule.term ?? ""}
                      onChange={(e) =>
                        patch({
                          rules: rules.map((r, i) =>
                            i === index ? { ...r, term: e.target.value } : r,
                          ),
                        })
                      }
                    />
                  </label>
                ) : (
                  <label>
                    Extracted field
                    <select
                      className="input"
                      value={rule.field ?? ""}
                      onChange={(e) =>
                        patch({
                          rules: rules.map((r, i) =>
                            i === index ? { ...r, field: e.target.value } : r,
                          ),
                        })
                      }
                    >
                      <option value="">Choose a field</option>
                      {fields.map((f, i) => (
                        <option key={i} value={f.name}>
                          {f.label || f.name}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {rule.type === "threshold" && (
                  <label>
                    Threshold amount
                    <input
                      type="number"
                      className="input"
                      value={rule.threshold ?? ""}
                      onChange={(e) =>
                        patch({
                          rules: rules.map((r, i) =>
                            i === index
                              ? {
                                  ...r,
                                  threshold:
                                    e.target.value === ""
                                      ? null
                                      : Number(e.target.value),
                                }
                              : r,
                          ),
                        })
                      }
                    />
                  </label>
                )}
                <label>
                  Severity
                  <select
                    className="input"
                    value={rule.severity ?? "medium"}
                    onChange={(e) =>
                      patch({
                        rules: rules.map((r, i) =>
                          i === index ? { ...r, severity: e.target.value } : r,
                        ),
                      })
                    }
                  >
                    {["low", "medium", "high"].map((severity) => (
                      <option key={severity}>{severity}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button
                type="button"
                className="mt-3 text-xs text-rose-700"
                onClick={() =>
                  patch({ rules: rules.filter((_, i) => i !== index) })
                }
              >
                Remove rule {index + 1}
              </button>
            </fieldset>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={Boolean(data.obligations)}
              onChange={(e) => patch({ obligations: e.target.checked })}
            />
            Identify obligation candidates
          </label>
        </>
      ) : (
        <p role="alert" className="error-box">
          Complete or correct the JSON definition below to use the form editor.
        </p>
      )}
      <details className="technical-details" open={!data || undefined}>
        <summary>Advanced JSON editor</summary>
        <label className="sr-only" htmlFor="template-json">
          Template JSON
        </label>
        <textarea
          id="template-json"
          className="input min-h-64 font-mono text-xs"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </details>
    </div>
  );
}
