"use client";

import { Fragment } from "react";
import { Icon } from "./ui";

// Plain React text only: model output is never interpreted as HTML.
export function AnswerText({
  text,
  sourceCount,
  onSource,
}: {
  text: string;
  sourceCount: number;
  onSource: (index: number) => void;
}) {
  return (
    <div className="answer-content">
      {text.split(/\n\n+/).map((paragraph, p) => (
        <p key={p}>
          {paragraph.split(/(\[\d+(?:,\s*\d+)*\])/).map((part, i) => {
            if (!/^\[\d+(?:,\s*\d+)*\]$/.test(part))
              return <Fragment key={i}>{part}</Fragment>;
            return (
              <span key={i} className="inline-citations">
                {part
                  .slice(1, -1)
                  .split(",")
                  .map((number) => {
                    const index = Number(number.trim()) - 1;
                    return index >= 0 && index < sourceCount ? (
                      <button
                        key={index}
                        type="button"
                        aria-label={`Inspect source ${index + 1}`}
                        className="citation-number"
                        onClick={() => onSource(index)}
                      >
                        {index + 1}
                      </button>
                    ) : (
                      <Fragment key={number}>{part}</Fragment>
                    );
                  })}
              </span>
            );
          })}
        </p>
      ))}
    </div>
  );
}

export type Usage = {
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | string | null;
};
export function UsageDetails({ usage }: { usage: Usage }) {
  const total =
    usage.input_tokens !== null && usage.output_tokens !== null
      ? usage.input_tokens + usage.output_tokens
      : null;
  const cost =
    usage.estimated_cost_usd !== null &&
    Number.isFinite(Number(usage.estimated_cost_usd))
      ? Number(usage.estimated_cost_usd).toLocaleString("en-US", {
          style: "currency",
          currency: "USD",
          minimumFractionDigits: 2,
          maximumFractionDigits: 6,
        })
      : "unavailable";
  return (
    <details className="usage-details">
      <summary>
        <Icon name="activity" />
        {usage.model}
        <span>·</span>
        {total === null
          ? "Usage unavailable"
          : `${total.toLocaleString()} tokens`}
        <span>·</span>Est. {cost}
      </summary>
      <p>
        {usage.model} · Input {usage.input_tokens ?? "unknown"} / output{" "}
        {usage.output_tokens ?? "unknown"} tokens · Estimated USD{" "}
        {usage.estimated_cost_usd ?? "unknown"}
      </p>
      <p>Estimate based on configured pricing; not a billing statement.</p>
    </details>
  );
}
