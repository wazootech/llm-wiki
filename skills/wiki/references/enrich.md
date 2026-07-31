# Enrich — ingest raw material into wiki pages

Turn raw source material (transcripts, repo evidence, decisions, notes) into
canonical wiki pages with semantic frontmatter, evidence links, and freshness
tracking. The wiki is not a scratchpad — it is synthesized, verified memory.

## Source priority

1. Direct user instruction in the current task.
2. Current source repository code, configuration, README, issues, PRs, and CI.
3. Accepted decisions and current-state pages already in the wiki.
4. Meeting notes, transcripts, private chats, or other raw notes.
5. External research, clearly marked by source type and date accessed.

## Workflow

1. Read the existing wiki context — start with any index or current-state page
   relevant to the topic before making assumptions or creating new pages.
2. Identify the evidence source: transcript, local source repo, GitHub issue,
   PR, docs page, meeting notes, or direct user instruction. Preserve source
   links or local raw-file references, but do not paste private dumps into
   canonical wiki prose.
3. Classify each claim (see claim status below).
   Do not upgrade a claim to accepted ownership, production behavior, pricing,
   public positioning, or launch commitment without explicit evidence or
   stakeholder confirmation.
4. Update existing pages before creating new ones. Registers are indexes;
   create or promote entity pages only when the item needs lifecycle tracking.
5. Keep semantic frontmatter current. Add or adjust saved queries when a
   recurring operating question cannot be answered from the existing wiki
   model.
6. Summarize durable conclusions in canonical pages. Keep raw notes separate
   when they are public-safe and useful for later traceability.
7. Verify (see verification below).

## Claim status

Use explicit status language:

- **Accepted** — durable decision or confirmed operating rule.
- **Current** — observed implementation or process state.
- **Proposed** — planned but not accepted or implemented.
- **Hypothesis** — belief to test.
- **Open question** — unresolved item needing owner input.

## Standards

- Prefer exact source facts over inference. Mark inference explicitly.
- Keep the wiki public-safe: no secrets, private customer data, private
  contact details, raw staff-chat dumps, or unnecessary transcript excerpts.
- Use standard Markdown links, ATX headings, semantic frontmatter, and
  sentence case below H1.
- When source code contradicts the wiki, inspect the source repo and update
  the wiki with the durable conclusion.
- End with a short change report: pages changed, source material used,
  verification run, and open questions.

## Verification

```bash
# Format, lint, and check
wiki -c wiki.yml fmt --check
wiki -c wiki.yml lint --strict
wiki -c wiki.yml check --strict

# Also run check with verbose output
wiki -c wiki.yml check -v
```
