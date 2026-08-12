# Exocortex Capture MVP: PRD v3 (restated)

**Status:** Ratified Aug 1, 2026. No PROPOSED items remain. This restatement introduces no new decisions.
**Supersedes:** PRD v1, PRD v2, tech spec v1, and the MVP design summary wherever they conflict.
**Owner:** Mitchell. Single user, solo build.
**Why this file exists:** the v3 artifact was written to a working container that has since been discarded. Content below is reconstructed from the ratified decisions of the Aug 1 sessions. Section 11 is new and flags what was never decided.

---

## 0. The core change

Two moves, discovered in sequence. The second is a consequence of the first.

**Move 1, from "MVP tech specs explained."** Every earlier document described the security layer wrong. It framed the capability broker as a mitigation: keep all three legs of the lethal trifecta (private data access, network egress, untrusted input) and survive the combination by mediating the agent's access to sensitive files.

That is not the design. **Leg one is removed, not mitigated. No LLM, local or remote, reads from or writes to sensitive data.** The broker is not an AI component and was never meant to be. It is deterministic code: a fixed operation list checked against a static rule set written by hand. A request matches an allowed operation and executes, or it is refused. No reasoning, no tokens, no judgment. The model knows the input types and formats the broker accepts and nothing further.

This maps to the Action-Selector pattern in Willison's prompt injection design patterns writeup, not the heavier CaMeL / Code-Then-Execute pattern. The distinction is the whole trust story. A broker-as-mitigation is a probabilistic defense, and a guardrail that catches 95% of attacks is a failing grade in security. Removing the leg is a proof.

**Move 2, the consequence.** If no model may touch sensitive data, sensitivity stops being a per-item property and becomes a location. Two stores:

| Store | Contents | Size | Model access |
|---|---|---|---|
| **vault** | User-authored sensitive information | Small | None, ever |
| **memex** | Captured content: articles, posts, later books | Large, growing | Full |

**The store an item lives in is its sensitivity label.** This deletes, rather than solves, three previously open problems: per-item sensitivity flags, the compute-boundary routing rule, and the entire mediated-access design space. Those existed only because one store held both kinds of data. With the split there is nothing to mediate. The model host process gets full memex access and no filesystem path to the vault.

---

## 1. What this supersedes

Carried here so the older documents in the project can be read without re-deriving the deltas.

| Prior position | Source | Current |
|---|---|---|
| Sensitive data sits behind a broker that mediates agent access | Design summary #3 | Superseded. Model never reaches sensitive data at all. Broker is deterministic code, and no vault feature ships in v1. |
| Curated allowlist for v1, no classifier | Design summary #5 | Amended. AIGC classifier is in scope for long-form, where detection actually works. Allowlist phases in with the feed, where it has a job. |
| Fidelity checking only, in v1 | Design summary #6 | Amended. Fidelity checking moves to backlog. Fallacy detection stays permanently out. |
| One aggregated feed across sources | Design summary #7 | Deferred to the browser phase. |
| Terse output as a constraint on generated summaries | Design summary #9 | Superseded. There are no generated summaries. The model emits labels, never prose. |
| Sensitivity as labels vs folders, unresolved | Design summary open #3 | Resolved by the store split. |
| Local vs remote compute boundary, unresolved | Design summary open #6 | Mooted for sensitivity. Replaced by the executor provenance rule (D17). |
| Retrieval trigger, unresolved | Design summary open #9 | Resolved: search only in v1. EOD ledger cut. |
| Platform scope, unresolved | Design summary open #10 | Resolved: generic, LessWrong, Substack. |
| Daily-driver browser replacing Chrome | Tech spec v1 | Deferred. MVP is a send-to-capture service. |
| CDP network tap, escape hatch, x.com adapter | Tech spec v1 | Deferred to the browser and short-form phases. |

---

## 2. Amended decisions

| # | Decision |
|---|---|
| **D15** | MVP delivery is a send-to-capture service, not a browser. It fetches only URLs the user sends and never navigates on its own. Daily-driver scope, escape hatch, and the CDP network tap are deferred to the browser phase. The vault/memex split is a day-one architecture commitment regardless. |
| **D16** | Memex canonical form is Markdown plus blobs, nothing else. All IR fields, tags, labels, and trust annotations live in Markdown frontmatter, with append semantics for trust entries. SQLite plus FTS5 is a derived, optional accelerator; deleting it loses nothing. v1 search may be grep-class over frontmatter. |
| **D17** | Labeling executes on the desktop only. The model may be local to the desktop or a named remote provider. Every label records its executor: host (`desktop`, `mobile`, `remote:<provider>`), model name, model version. Mobile never labels. |

---

## 3. Product definition

**Problem.** Long-form content consumed across the web is lost the moment it scrolls past. Existing capture tools fail on trust, quality, or ownership. An increasing share of published text is machine-generated with no signal attached to say so.

**Product.** A capture service. Send a URL from the Mac or the Android phone. The service fetches the page, normalizes it into the IR, stores Markdown plus the original bytes in the memex, labels it by machine, and makes it findable by search. The vault holds sensitive user-authored data and no model touches it.

**Content phasing.** v1: long-form articles (LessWrong, Substack, generic pages). Phase 2: books. Phase 3: short-form and the owned browser.

**One-line test.** A URL shared from the phone at noon exists in the memex by evening as Markdown plus original bytes, carries machine-assigned labels with a named executor, and a tag search on the Mac finds it. Both stores stay readable in any text editor forever.

---

## 4. Scope

**In**
- macOS capture service, Electron-hosted, using a hidden BrowserWindow render when an adapter requires it
- Mac quick-capture entry: global hotkey accepting a URL
- Android share-target pushing URLs one-way over a Tailscale HTTPS endpoint
- Adapters: generic, LessWrong, Substack. LessWrong is client-rendered, so its adapter uses headless render or the site's GraphQL API; a spike decides which
- Memex: Markdown plus blobs. MHTML snapshot on for adapter captures, off for generic
- Capture-time labeler: tags, topic, author, content type
- AIGC classifier, long-form only, verdict written to the trust slot
- Optional derived SQLite/FTS5 index
- Vault directory plus the INV-1 CI guard from day one

**Phased**
- Books (phase 2)
- Owned browser: daily driver, CDP tap, escape hatch, feed, allowlist gating, retrieval triggers including the EOD ledger (phase 3)
- Short-form content and the x.com adapter (phase 3)

**Backlog**
- Fidelity checking, generated summaries, on-navigate surfacing, Wayback integration

**Out**
- Multi-user, sharing, network layer, proof-of-personhood, OS build, monetization, fallacy and reasoning-quality detection

---

## 5. Requirements

**R1. Capture is one-shot and lossless.** The fetched HTTP payload is the original-bytes record: hash it, store it. Adapter captures also store MHTML. Assume re-fetching later is impossible.

**R2. Files are the product.** The memex is fully functional with zero SQLite. Search must not require the index. Grep-class search over frontmatter satisfies v1.

**R3. Capture is explicit.** Nothing enters the pipeline without a user send. The service initiates network activity only to fetch a sent URL or to reach a configured model provider.

**R4. Labels over prose.** The system annotates, never narrates. No generated summaries anywhere in the product.

**R5. Trust is deterministic where it can be.** Author scores accrue over time. The classifier verdict is a label sitting beside them, never a sole gate. The allowlist phases in with the feed.

**R6. Satellite capture is unattended.** An Android share arrives in the memex with no further step on either device.

---

## 6. System invariants

**INV-1.** No LLM, local or remote, reads from or writes to the vault. Memex access is unrestricted. Enforced structurally and verified by a CI test that fails the build if the model host process can open a vault path.

**INV-2.** Vault operations are deterministic code only. No model-invocable vault operation exists.

**INV-3.** Every machine-produced label records executor host, model name, model version, and the item that produced it.

**INV-4.** Every item carries the ratified IR fields: stable author identifier, retrieval timestamp, byte hash, per-block structural role, provenance chain, trust annotation slot, tags.

**INV-5.** Outbound network activity is limited to fetching sent URLs and reaching configured model providers. Nothing else leaves the machine.

---

## 7. Architecture summary

**Processes.** Capture service core, which owns both stores and all deterministic rules. Model host, which has memex read access, no vault path, desktop only. Android client, push only.

**Data.** `memex/` holds Markdown with full frontmatter. `blobs/` holds raw bytes and MHTML. Trust annotations append into frontmatter so index rebuilds are lossless. Optional SQLite index carries tags tables and FTS5 and is rebuildable by one command. Identity is a local ULID with handle mapping.

**Model surfaces.** Exactly two: the capture-time labeler and the AIGC classifier. Both run under D17's executor rule, behind the thin provider abstraction.

**Vault.** A directory, populated only by the user, guarded by the CI test. Features on it come later. The boundary exists now.

---

## 8. Build order

1. Memex layout, frontmatter writer, vault directory, INV-1 CI test
2. Generic adapter: fetch, extract, Markdown plus hashed bytes
3. Substack adapter plus MHTML
4. LessWrong adapter, render-vs-GraphQL spike first
5. Android share-target plus Tailscale endpoint on the Mac
6. Labeler with executor provenance
7. Classifier
8. Optional SQLite/FTS5 index plus rebuild command

---

## 9. Acceptance criteria

1. Send a LessWrong URL on the Mac. The item lands in the memex with Markdown, raw bytes, MHTML, and complete frontmatter per INV-4.
2. Same for a Substack URL.
3. A generic URL produces Markdown plus raw bytes.
4. An Android share at noon produces an identical result on the Mac via Tailscale with no manual step.
5. Every label on those items carries executor host, model name, and model version.
6. A tag search returns the right item. If the SQLite index exists: delete it, rebuild from files, get identical results.
7. The CI guard fails the build when the model host is given a vault path.
8. The classifier writes an AI-likelihood label into the trust slot for a long-form test set, and that label is searchable.

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| LessWrong client-side rendering complicates extraction | Spike render vs GraphQL before committing the adapter |
| Light editing degrades AI detection even on long-form | Verdict is one label beside author score, never a sole gate |
| Frontmatter-as-canonical needs append discipline or rebuilds lose data | Label and trust writers are append-only by construction; criterion 6 catches regressions |
| Adapter rot | Substack and LessWrong churn slowly; MHTML preserves the capture when extraction breaks |
| Search-only retrieval defers the exocortex claim | Accepted for v1. Retrieval triggers return with the browser phase |

---

## 11. Genuinely open, not previously decided

Flagged because they were never answered, not because they are being reopened.

1. **Author score source.** R5 says scores accrue over time. Nothing in the v1 build produces a score. Either the scoring input is specified, or R5 is honestly a phase-3 requirement and v1 ships with an empty author record.
2. **Broker return path.** Whether anything comes back from the broker into the model's context is what separates Action-Selector from Plan-Then-Execute, and it changes the security claim. Moot for v1, since no vault feature ships. Blocking before the first one does.
3. **Success measurement.** For a single-user tool, adoption metrics are noise. The acceptance criteria in section 9 are the only meaningful pass condition. If a signal is wanted later, capture-to-retrieval rate is the honest one: what fraction of captured items are ever returned by a search.
4. **Blob retention ceiling.** Raw bytes plus MHTML per capture has no stated cap or eviction rule. Not blocking build item 1.

---

## 12. Glossary

- **IR (intermediate representation):** the one canonical object every capture becomes, regardless of source.
- **Byte hash:** fingerprint of the exact downloaded bytes. Proves integrity, catches duplicates.
- **Per-block structural role:** each chunk of a page tagged as body, comment, navigation, or ad.
- **Provenance chain:** the recorded path from raw bytes to Markdown to labels.
- **Trust annotation slot:** reserved frontmatter field where verdicts attach without a schema change.
- **Executor:** the host and model that produced a label (`desktop`, `mobile`, `remote:<provider>`).
- **MHTML:** single-file snapshot of a rendered page.
- **CI:** continuous integration. Automated tests that run on every code change and can fail the build.
- **ULID:** unique identifier that sorts by creation time.
- **FTS5:** SQLite's full-text search engine.
- **Adapter:** per-site extraction rules that turn a page into the IR.
- **Vault:** the sensitive store. No model access.
- **Memex:** the captured-content store. Full model access.
- **Action-Selector:** agent pattern where the model can trigger a fixed set of operations but receives nothing back from them.
