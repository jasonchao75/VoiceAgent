# ASR Evaluation UI Annotations

- Risk: high
- Baseline viewports: 1440 × 1000 desktop; 1024 × 1000 narrow; 390 × 844 minimum mobile overflow check
- Device scale: 1
- Theme: dark
- Baseline locales: English and Chinese
- Strict regions: product navigation, batch stage order, review evidence/decision hierarchy, report entry, Benchmark filter/download toolbar, dialog/drawer ownership
- Adaptive regions: table pagination, translated text wrapping, tag count, provider/model catalog values, long transcripts
- Dynamic masks: timestamps, active-request elapsed seconds, task progress animation, cost values, audio progress and signed URLs only

| Region | Size/layout | Required behavior | States | Delta Scenario |
|---|---|---|---|---|
| Product rail | 48 px product rail + 270 px Evaluation side navigation on desktop | Evaluation pages remain separate from Bot configuration | active/hover/narrow | Bilingual evaluation UI |
| Batch list | Full main workspace with metric row and table | Running rows show only current active requests, one row per concurrent request with a ticking elapsed time; paused/partial rows show only failed and succeeded counts | running/paused/review/completed/partial/error | Evaluation metrics; live external-request visibility |
| New batch dialog | Width bounded by viewport; vertical scroll only | Explain three directories and per-conversation files; freeze resources | empty/invalid/repaired/ready | Per-conversation package contract |
| Stage detail | Five ordered stage cards | Show each active conversation-level ASR or LLM request separately with provider, ordinal/total and elapsed time; backend checkpoints remain authoritative and stale heartbeat is visibly distinct | active/done/partial/retry/stale | Conversation ASR reuse; live external-request visibility |
| Review queue | Left queue + right review at desktop; stacked narrow | One queue item equals one target user event | pending/active/submitted | Explicit manual review |
| Review comparison | Historical transcript and current proposed label adjacent desktop, stacked narrow | Neither provider is ground truth; no default candidate | empty/candidate/manual/unclear | Submit Good/Bad/unclear |
| Decision actions | Good and Bad visually distinct; unclear secondary | Good names production correctness; Bad requires label | enabled/disabled/pending | Submit Good; Submit Bad |
| Technical evidence | Collapsed by default | Segment IDs and original ranges remain non-primary | collapsed/expanded/missing | Unified playback interval |
| Report | Batch-owned report index/detail | Preliminary/final immutable versions and coverage visible; AI-proposed tag name and description are reviewed together and both persist on creation; complete Case details filter by scenario tag without mutating the report; each Case audio expands inline with pause/resume, seek and elapsed/total time | preliminary/final/partial/tag-proposed/tag-created/filtered/audio-playing/audio-paused | Immutable reports; AI-proposed tag creation; report Case filtering; unified playback interval |
| Conversation drawer | Right drawer with sticky full-call player | Full event history; selected event highlighted and seek synchronized | loading/ready/unavailable/long | Report production observations |
| Benchmark | Filters + 20-row pageable table + two download actions | Cross-page selected IDs or every all-page filter match; ZIP groups WAV by language then primary scenario tag | empty/filtered/selected/generating/partial | Selected and all-filtered grouped download |
| Scenario tags | Data-backed cards + new/edit/delete actions | Edit saves a new version; delete removes from current taxonomy while referenced historical snapshots remain readable | default/editing/delete-confirmed/removed | Create, edit, delete |
| Configuration | Tags, contexts, reference dictionaries, Prompts, connections, costs | Context create/edit opens a complete versioned form and exposes the source of every runtime LLM input; the context list and editor preview show the variable-bearing template beside the fully rendered Prompt, with clickable field correspondence and all dictionary entries; generic dictionaries are versioned and linked to contexts; prepared RiyadBank data is prefilled; both complete Chinese Prompts default to read-only, require an explicit edit action, use `reference_dictionaries`, and validate their required contracts | clean/dirty/invalid/conflict/version-saved/preview-pass-1/preview-pass-2/field-highlight | Configuration specs |
| All overlays | `max-width: 100%`, shrinkable children | `scrollWidth <= clientWidth`; necessary vertical scroll only | desktop/narrow/long content | Overflow-safe UI |

## Non-negotiable review content

- English mode contains no Chinese UI residue, including fixed fixture context.
- Historical transcript and current proposed label are visually adjacent.
- Good and Bad are explicit actions; a generic “save” cannot hide the classification.
- Unclear copy says “reviewed, excluded from Benchmark.”
- Full conversation IDs are never shortened.
- Additional Good origin and suspect-reclassified Good origin are distinguishable in Library/report details.
- An AI-proposed tag always displays and creates both its bilingual name and bilingual description; name-only creation is invalid.
- Prototype-only static counts and fake player behavior must not be presented as live production data.
- Elapsed seconds are visual only and `aria-hidden`; assistive technology announces request start, completion, failure or stale-heartbeat state changes, never every second.
- Prepared context and Prompt content must be seeded idempotently before launch; a redeploy cannot overwrite administrator-created versions.
- `branch_dictionary` is not a platform field. Business-specific dictionaries are generic versioned resources linked from a context and rendered as `reference_dictionaries` for both passes.
