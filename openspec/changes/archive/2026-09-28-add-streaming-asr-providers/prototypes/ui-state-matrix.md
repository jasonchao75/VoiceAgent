# UI State Matrix

| Scenario ID | Page/region | Fixture | Data state | Interaction/error state | Viewport | Delta Scenario | Evidence |
|---|---|---|---|---|---|---|---|
| ASR-01 | ASR drawer | Deepgram legacy Bot | valid | Deepgram selected | 1440×1000 | Edit legacy Bot | Prototype interaction |
| ASR-02 | ASR drawer | New Speechmatics Bot | valid | Speechmatics Advanced | 1440×1000 | Configure enhanced | Prototype interaction |
| ASR-03 | ASR drawer | New Soniox Bot | valid | Static Context visible | 1440×1000 | Configure Soniox context | Prototype interaction |
| ASR-04 | ASR drawer | New AssemblyAI Bot | valid | Full Context controls | 1440×1000 | Configure context modes | Prototype default |
| ASR-05 | ASR drawer | New AssemblyAI Bot | valid | Context toggles off | 1440×1000 | Context disabled | Prototype interaction |
| ASR-06 | ASR drawer | Long help/terms | valid | wrapped content | 390×844 | Prevent overflow | Prototype responsive |
| ASR-07 | ASR drawer | Provider/model capability matrix | valid | Provider native / Off; unavailable Off is disabled with reason | both | Select Turn Detection source | Prototype interaction |
| ASR-08 | ASR drawer | Catalog unavailable | error | controls disabled + retry | both | Catalog failure | Checkpoint A fixture required |
| ASR-09 | ASR drawer | Bot-scoped Provider keys | mixed availability | switch Provider; blank input keeps this Bot's matching saved key | both | Switch provider key | Prototype interaction |
| ASR-10 | Web Call | Valid Bot | runtime error | auth/rate-limit/timeout | both | Safe provider failure | Checkpoint B real/mock |
| ASR-11 | ASR drawer | New AssemblyAI Bot | valid | language_codes empty = auto; open 18-language picker; select multiple | both | Configure AssemblyAI language steering | Prototype interaction |
| ASR-12 | ASR drawer | Deepgram legacy Bot | valid | online-equivalent Advanced field order | both | Preserve current Deepgram controls | Prototype visual comparison |
| ASR-13 | ASR drawer | Saved Bot Provider key | valid | Key appears after Advanced; blank keeps this Bot's saved key; no Use saved key action | both | Isolate provider keys across bots | Prototype interaction |
| ASR-14 | ASR drawer | Speechmatics Discovery fixture | valid | Full Language Pack list; `ar_en` default; domain options follow selected Pack; no `auto` | both | Select a Speechmatics language pack | Prototype interaction |
| ASR-15 | ASR drawer | Soniox `stt-rt-v5.languages[]` fixture | valid | Open searchable 60-language picker; add/remove hints; clear to automatic | both | Select Soniox language hints | Prototype interaction |
| ASR-16 | ASR drawer | Deepgram Nova-3 | valid | switch from Flux; Source fixed Off; Provider native disabled; positive V1 Endpointing silence plus recognition/format fields replace Flux V2 fields | both | Configure Deepgram Nova-3 | Prototype interaction |
| ASR-17 | ASR drawer | Soniox | valid | Source fixed Provider native; Off disabled; native endpoint controls remain visible | both | Apply fixed Turn source capability | Prototype interaction |
| ASR-18 | ASR drawer | Speechmatics | valid | select Off; mode locks to Fixed silence, positive Silence trigger remains visible, max-delay intelligence hides; help rejects threshold 0 | both | Use Speechmatics VAD-only turn detection | Prototype interaction |
| ASR-19 | ASR drawer | AssemblyAI | constrained | Source fixed Provider native; Off disabled because U3.5 Pro has no Provider-side VAD-only mode | both | Apply fixed Turn source capability | Prototype interaction |
| ASR-20 | ASR drawer | Speechmatics Advanced | valid | sentence emission remains distinct from EndOfTurn; Maximum EOU starts at 10.0 s with dynamic minimum; permitted marks switches between `all` and a custom list | both | Configure Speechmatics advanced contract | Prototype interaction |
| ASR-21 | ASR drawer | AssemblyAI Advanced | valid | each Mode resets three Turn values to its official preset; manual edit marks the selected Mode modified; VAD threshold remains independent | both | Configure AssemblyAI Mode with editable preset values | Prototype interaction |
