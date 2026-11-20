# Suggested LinkedIn publishing plan

This is an editorial recommendation, not a claim about reach or LinkedIn's algorithm.

## Post 1 — Project announcement

Use `linkedin-post.md` (or the shorter alternative) with the **eight-slide carousel
PDF**. Upload it as a document; the PDF already contains real product screenshots.
Do not repeat all the screenshots as extra attachments or publish every asset at once.
The eight-page case study is for your portfolio/Featured section or people who want
the deeper technical explanation; it is not a second attachment needed for launch.

LinkedIn's document upload instructions:
https://www.linkedin.com/help/linkedin/answer/a519831

## Post 2 — Engineering follow-up

Roughly a week later, share a different angle: how evidence moves from retrieval to
human review and operational ownership. Attach **four real screenshots**, in order:

1. `screenshots/post-ready/dark/03-assistant.png` — dark Assistant; retain the visible
   mock label and describe it as an extractive development preview.
2. `screenshots/post-ready/light/01-dashboard.png` — light dashboard; real counts of
   fictional demo records, not claimed customer outcomes.
3. `screenshots/post-ready/light/08-comparison.png` — actual before/after comparison.
4. `screenshots/post-ready/dark/09-operations.png` — organization-wide workflows.

These files are 2880 × 2000 viewport screenshots from the actual app. Full-page images
and focused crops remain available for closer inspection. Review the image preview
before publishing; any platform crop should keep the mock/provenance labels visible.

Do not repeat the entire announcement. Discuss one concrete tradeoff, such as
application-managed citations, source revision validity, or PostgreSQL job recovery.
There is no need for nine posts just because the project had nine phases. A third
post is optional only when you have a genuinely different lesson or new work to show.

## If you only want one post

Use the carousel announcement. It tells the complete project story and includes
product proof. Keep the separate screenshots for your portfolio and later discussion.

Replace the repository placeholder, retain personal-project/demo disclosures, and
keep the Fiza Ahmad branding in the regenerated carousel. No simulated response
should be described as a genuine GPT result.

## Correctly describe the paid API validation

The launch carousel now includes a real manual GPT-6 Luna test record and the
cost-conscious architecture. Mention that successful paid local Q&A validation in
the post. It is separate from the product screenshots, which remain labeled mock.
No additional paid calls were made for asset generation; this does not mean the
application was never tested with a paid API. The follow-up can explain local
embeddings, scoped retrieval, token accounting and budgets. Do not claim measured
savings or comparative model accuracy. See `live-validation.md` for the evidence scope.

When explaining the architecture, use the complementary roles shown on slide 4:
local embeddings retrieve authorized evidence; GPT generates grounded intelligence;
deterministic rules and human workflows add reliability and control. Structured AI
reads selected revisions directly. Avoid suggesting that vectors generate prose or
that GPT merely reviews deterministic results. The full diagram is available in
`architecture/documind-architecture.png`; the carousel presents a mobile-friendly
summary instead of shrinking the full diagram into a slide.
