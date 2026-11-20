// Synthetic data for an isolated visual-test server ONLY. Never imported by the app.
const id = (n) => `aaaaaaaa-aaaa-4aaa-8aaa-${String(n).padStart(12, "0")}`;
export const org = id(1),
  otherOrg = id(2),
  runId = id(30),
  compareId = id(31),
  docId = id(10);
const user = { id: id(3), name: "Alex Morgan", email: "alex@example.test" };
const organizations = [
  { id: org, name: "Northstar Labs", role: "admin" },
  { id: otherOrg, name: "Research Workspace", role: "member" },
];
const quote =
  "The annual service fee is USD 50,000, payable within 30 days of invoice. The supplier shall provide quarterly security reviews and notify the customer of material incidents within 48 hours.";
const evidence = {
  section_id: id(40),
  revision_id: id(41),
  page_number: 3,
  label: "Page 3 · Commercial terms",
  start: 0,
  end: quote.length,
  quote,
};
const filenames = [
  "Master Services Agreement.pdf",
  "Data Processing Addendum.docx",
  "Enterprise Security Policy.pdf",
  "Supplier Onboarding Guide.pdf",
  "Q4 Compliance Review.docx",
  "Procurement Guidelines.txt",
  "Service Level Agreement.pdf",
];
const documents = filenames.map((filename, i) => ({
  id: id(10 + i),
  organization_id: org,
  uploader_id: user.id,
  filename,
  format: filename.split(".").at(-1),
  size_bytes: 148000 + i * 16300,
  status: i === 5 ? "processing" : "completed",
  index_status: i === 5 ? "pending" : "completed",
  error: null,
  index_error: null,
  section_count: i === 5 ? 0 : 8 + i,
  chunk_count: i === 5 ? 0 : 23 + i,
  character_count: 23000,
  storage_ready: true,
  chunk_size: 1200,
  chunk_overlap: 200,
  source_metadata: { pages: 12, extraction: "Native PDF text" },
  created_at: `2026-11-${String(20 - i).padStart(2, "0")}T09:30:00Z`,
}));
const source = {
  source_id: id(50),
  document_id: docId,
  filename: filenames[0],
  label: evidence.label,
  page_number: 3,
  text: quote,
  quote,
  similarity: 0.89,
};
const usage = {
  model: "gpt-test-fixture",
  input_tokens: 1240,
  output_tokens: 286,
  estimated_cost_usd: "0.001812",
};
const run = {
  id: runId,
  mode: "extract",
  engine: "openai",
  state: "completed",
  error: null,
  coverage: { complete: true, sections: 12, characters: 23000 },
  left_revision_id: evidence.revision_id,
  right_revision_id: null,
  created_at: "2026-11-20T10:30:00Z",
};
const comparison = {
  ...run,
  id: compareId,
  mode: "compare",
  right_revision_id: id(42),
  created_at: "2026-11-19T11:00:00Z",
};
const fields = [
  {
    id: id(60),
    name: "contract_value",
    kind: "field",
    original: {
      raw: "USD 50,000",
      value: { currency: "USD", amount: "50000" },
      type: "money",
      provenance: "openai",
      review_required: true,
    },
  },
  {
    id: id(61),
    name: "Payment exposure",
    kind: "risk",
    original: {
      severity: "medium",
      note: "Review the payment window against internal approval timelines.",
      provenance: "openai",
      review_required: true,
    },
  },
  {
    id: id(62),
    name: "Quarterly security review",
    kind: "obligation",
    original: {
      commitment: "The supplier shall provide quarterly security reviews",
      responsible_party: "The supplier",
      deadline: null,
      note: "Confirm review ownership and the reporting schedule.",
      provenance: "openai",
      review_required: true,
    },
  },
].map((item) => ({
  ...item,
  run_id: runId,
  organization_id: org,
  evidence: [evidence],
  corrected: null,
  validation: item.kind === "field" ? "valid" : "candidate",
  review_status: "pending",
  obligation_status: "open",
  version: 1,
  can_review: true,
  can_assign: true,
  filename: filenames[0],
  template_name: "Commercial review",
  engine: "openai",
  document_id: docId,
  effective_validation: "valid",
  contract_deadline: item.kind === "obligation" ? "2026-12-01" : null,
  assignment_due_date: "2026-11-27",
  assignee_id: user.id,
  assignee_name: user.name,
  responsible_party: item.original.responsible_party ?? null,
  severity: item.original.severity ?? null,
  is_current: true,
  source_superseded: false,
  analysis_superseded: false,
  is_done: false,
}));
const changes = [
  {
    ...fields[0],
    id: id(63),
    kind: "change",
    name: "Modified",
    original: {
      before: "The annual service fee is USD 40,000.",
      after: "The annual service fee is USD 50,000.",
      ai_explanation:
        "The annual fee has increased by USD 10,000. Review the revised commercial commitment before approval.",
      provenance: "openai",
      review_required: true,
    },
    evidence: [evidence],
  },
];
const events = [
  "review_approved",
  "assignment_updated",
  "obligation_status_updated",
].map((action, i) => ({
  id: id(80 + i),
  item_id: fields[i].id,
  run_id: runId,
  engine: "openai",
  actor_id: user.id,
  actor_name: user.name,
  action,
  reason: "Checked the original source and confirmed next steps.",
  created_at: `2026-11-${20 - i}T10:00:00Z`,
  source_unavailable: false,
  before: { status: "pending" },
  after: { status: "approved" },
}));

export function fixture(path, method) {
  const url = new URL(path, "http://localhost");
  const p = url.pathname.replace(/^\/api\/v1/, "");
  if (p === "/auth/me") return user;
  if (p === "/auth/csrf") return { csrf_token: "visual-test-only" };
  if (p.startsWith("/auth/")) return { status: "ok" };
  if (p === "/health/ready")
    return { status: "ok", database: "ok", pgvector: "ok" };
  if (p === "/health") return { status: "ok" };
  if (p === "/organizations") return organizations;
  const empty = p.includes(otherOrg);
  if (p.endsWith("/intelligence/status"))
    return {
      embeddings_enabled: true,
      provider: "openai",
      is_mock: false,
      model: usage.model,
      documents: empty ? [] : documents,
    };
  if (p.endsWith("/conversations"))
    return method === "POST"
      ? { id: id(90), title: "Commercial terms & obligations" }
      : empty
        ? []
        : [
            { id: id(90), title: "Commercial terms & obligations" },
            {
              id: id(91),
              title:
                "Supplier security commitments and professional skills documentation for the enterprise procurement review committee",
            },
          ];
  if (p.endsWith("/messages")) {
    const message = {
      id: id(92),
      question: "What are the key commercial terms and supplier obligations?",
      answer:
        "The agreement sets an annual service fee of USD 50,000, with payment due within 30 days of invoice. [1]\n\nThe supplier must provide quarterly security reviews and report material incidents within 48 hours. These commitments should be reviewed alongside your internal payment and security approval processes. [1]",
      state: "completed",
      provider: "openai",
      is_mock: false,
      citations: [source],
      usage,
    };
    return method === "POST" ? message : [message];
  }
  if (p.endsWith("/search")) return { sources: [source] };
  if (p.endsWith("/operations/summary"))
    return {
      totals: {
        records: empty ? 0 : 3,
        risks: empty ? 0 : 1,
        obligations: empty ? 0 : 1,
        pending_reviews: empty ? 0 : 2,
        open_obligations: empty ? 0 : 1,
        overdue_obligations: 0,
        upcoming_obligations: empty ? 0 : 1,
        open_assignments: empty ? 0 : 2,
        unresolved: 0,
      },
      severity: empty ? {} : { medium: 1 },
      inventory: {
        documents: empty ? {} : { completed: 6, processing: 1 },
        analyses: empty ? {} : { completed: 2 },
      },
      filters: { as_of: "2026-11-20" },
      counting: "Current analysis records; templates and engines may overlap.",
      date_basis: "UTC contract dates",
    };
  if (p.endsWith("/activity"))
    return { items: empty ? [] : events, total: empty ? 0 : events.length };
  if (p.endsWith("/operations/items"))
    return {
      items: empty
        ? []
        : fields.filter(
            (item) =>
              !url.searchParams.get("kind") ||
              item.kind === url.searchParams.get("kind") ||
              url.searchParams.get("kind") === "review",
          ),
      total: empty ? 0 : fields.length,
    };
  if (p.endsWith("/operations/members"))
    return [{ id: user.id, name: user.name }];
  if (p.endsWith("/members"))
    return [
      { user_id: user.id, name: user.name, email: user.email, role: "admin" },
      {
        user_id: id(4),
        name: "Jordan Lee",
        email: "jordan@example.test",
        role: "member",
      },
    ];
  if (p.endsWith("/config")) return { upload_max_bytes: 20971520 };
  if (p.endsWith("/documents"))
    return {
      items: empty
        ? []
        : documents.slice(0, Number(url.searchParams.get("page_size") ?? 20)),
      total: empty ? 0 : documents.length,
      page: 1,
      page_size: 20,
    };
  if (p.endsWith("/content"))
    return {
      document_id: docId,
      total: 1,
      page: 1,
      page_size: 5,
      sections: [
        {
          id: evidence.section_id,
          ordinal: 0,
          label: evidence.label,
          page_number: 3,
          text: quote,
        },
      ],
    };
  if (p.endsWith("/revisions"))
    return [
      { id: evidence.revision_id, current: true, created_at: run.created_at },
    ];
  if (p.endsWith("/structured/templates"))
    return [
      {
        id: id(100),
        name: "Commercial review",
        definition: {
          fields: [
            {
              name: "contract_value",
              label: "Contract value",
              type: "money",
              required: true,
            },
          ],
          rules: [],
          obligations: true,
        },
      },
    ];
  if (p.endsWith("/structured/runs")) return empty ? [] : [run, comparison];
  if (p.endsWith("/sections"))
    return {
      items: [
        {
          id: evidence.section_id,
          label: evidence.label,
          page_number: 3,
          text: quote,
        },
      ],
      total: 1,
      page: 1,
    };
  if (p.includes("/structured/runs/")) {
    const compare = p.endsWith(compareId);
    return {
      run: compare ? comparison : run,
      items: empty ? [] : compare ? changes : fields,
      reviews: [],
      can_manage: true,
      superseded: false,
      sources: [
        { revision_id: evidence.revision_id, filename: filenames[0] },
        ...(compare
          ? [
              {
                revision_id: id(42),
                filename: "Master Services Agreement v2.pdf",
              },
            ]
          : []),
      ],
      usage,
    };
  }
  if (/\/documents\/[0-9a-f-]+$/.test(p))
    return documents.find((d) => p.endsWith(d.id)) ?? documents[0];
  return { status: "ok" };
}
