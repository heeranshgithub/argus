# Product Improvements

**Audience:** the reviewer. Written from a seller's point of view, not a code one.
(Fits two printed pages.)

## 1. Five weaknesses in the current product

1. **Sessions are one-shot.** You can't refine the brief inline ("focus on their
   security posture") — you re-run from scratch.
2. **No comparison view.** You can't research two competitors side by side, which
   is exactly how an AE preps a displacement pitch.
3. **No shareable output.** The report lives in the app; there's no polished link
   or PDF to drop into a deal room or hand a buyer.
4. **Sources go stale silently.** Research from last week may be wrong by the
   meeting; there's no freshness check before you walk in.
5. **No CRM integration.** Everything is copy-paste back into Salesforce/HubSpot —
   the "copy-paste tax" that kills adoption of tools like this.

(Bonus: no team library — every rep re-researches the same accounts.)

## 2. Top 3 improvements to build next

1. **Sharing & export** — one-click PDF + a read-only link for the meeting card.
2. **CRM sync** — push the briefing to the matching HubSpot/Salesforce record;
   pull the account/contact context back in.
3. **Saved playbooks** — define a research recipe once, re-run it against a list
   of accounts (territory planning, event prep).

## 3. Who buys, who uses, why they pay

- **Buyer:** VP Sales / Head of GTM — owns rep productivity and ramp.
- **User:** AE / SDR preparing for meetings and outbound.
- **Why they pay:** ROI on AE time. If prep drops from ~30 min to ~5 min per
  meeting and call quality rises, the tool pays for itself across a team in days.
  Willingness-to-pay tracks seats × time-saved, not feature count.

## 4. Success metrics

- **North star:** research-prep time per meeting (target **30 min → 5 min**).
- **Inputs:** report quality score (human-rated sample), report→meeting
  conversion, daily/weekly active sellers, chat messages per session (engagement
  with the grounded copilot), share/export rate.
- **Guardrail:** citation-coverage (% of claims backed by a real source) — speed
  must not cost trust.

## 5. Four-week AI roadmap

- **Week 1** — embedding-based retrieval + reranker (replace BM25) for sharper,
  semantic chat grounding at scale.
- **Week 2** — eval harness + prompt regression tests so model/prompt changes are
  guarded in CI.
- **Week 3** — signal freshness checks + scheduled re-runs (auto-refresh before a
  calendared meeting).
- **Week 4** — persona-specific outreach generation (CISO vs. CFO vs. VP Eng).

## 6. Biggest cost / scaling / reliability risks

- **Cost:** per-run LLM spend. *Mitigation:* per-node model tiering (cheap models
  for planning/quality, strong for synthesis), a source budget, and a per-run
  cost cap.
- **Scaling:** in-process background tasks cap concurrency. *Mitigation:* migrate
  runs to a real queue with backpressure.
- **Reliability:** OpenRouter outage stalls all LLM calls. *Mitigation:* fallback
  model chain + a direct-provider escape hatch behind the same `LLMClient`
  protocol.

## 7. One feature to remove

The manual **"Resume from checkpoint"** button. Always-on resume is the better
UX; exposing resume as an explicit action leaks an implementation detail the
seller shouldn't have to think about.

## 8. One feature to add

A **"Meeting card"** — a one-page, genuinely printable/sellable export (PDF) built
around the meeting, not the search: who, why now, the one signal to open with,
three questions to ask, and the objection to expect.

## 9. First 90-day roadmap

- **Days 1–30:** ship sharing + export and CRM sync; swap chat retrieval to
  embeddings.
- **Days 31–60:** eval harness + persona-specific outreach generation.
- **Days 61–90:** scheduled re-runs + freshness alerts, and Slack delivery of the
  meeting card.

## 10. What I'd change first if I owned this product

Stop calling it a **"report"** — call it a **"briefing"** — and design the entire
UI around the *meeting*, not the search.
