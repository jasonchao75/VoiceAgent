# Streaming ASR Providers Prototype

Status: **User Gate 1 confirmed — D-019/D-020 User Gate 2 feedback amendment frozen.**

- Frozen file: `index.html`
- SHA-256: `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`
- Confirmation date: 2026-09-28
- Confirmation source: Current Codex task; D-014/D-015 Gate 1 confirmation plus D-019 quote “A。” and D-020 quote “另外，能不能把soniox和assembly的language hint后面的语言代码加一个括号，说明是什么语言呢？两个字母看着不方便”

Open `index.html` directly in a browser. The prototype reuses the current VoiceAgent dark product rail, Bot Settings page, three Pipeline cards and non-modal right ASR drawer. It does not contact any provider, persist a Key, or represent completed implementation.

## Review path

1. Confirm the ASR card remains part of the existing Pipeline layout.
2. In the right drawer, use the Provider dropdown to switch among Deepgram, Speechmatics, Soniox and AssemblyAI.
3. Verify Model, the Provider's real language control and Advanced fields fully replace each other; for Deepgram switch Flux/Nova-3 and confirm V2 EOT fields never mix with V1 Endpointing fields; for Speechmatics confirm the full Language Pack Catalog/domain linkage, sentence Segment explanation, `10.0 s` Maximum EOU default and All/Custom permitted marks control; for Soniox open `Add language hint`, search the 60-language model Catalog by code or English name, confirm entries render as `code (name)`, select/remove items and clear to Automatic; confirm Speechmatics/Soniox use the compact account-Catalog refresh action and the current-Bot Key section follows Advanced.
4. Review Turn detection source capability states: Soniox and AssemblyAI are fixed to Provider native with Off disabled; Nova-3 is fixed to Off and keeps positive V1 silence endpointing; Speechmatics Off fixes mode to Fixed silence and requires a positive `end_of_utterance_silence_trigger`.
5. On AssemblyAI, open `language_codes` steering and review the 18 unique `code (English name)` choices; switch all three Modes and confirm each selection resets Min silence / Max silence / Interruption delay to its official preset, then edit a value and confirm the Mode is marked modified; review the independent VAD threshold explanation, Prompt, Keyterms, Agent Context and User Context Carryover.
6. Resize to a narrow viewport and verify the drawer becomes a single column without horizontal scrolling.

## Traceability

| Prototype region | Delta Requirement / Scenario |
|---|---|
| Provider dropdown | `bot-config` / Select a streaming ASR provider |
| Model/Provider-specific language/Audio | `bot-config` / Catalog-backed Bot validation; AssemblyAI language steering; Speechmatics Language Pack selection; Soniox language hint selection |
| Bot-scoped component/provider credential after Advanced | `bot-config` / Optional encrypted key storage; isolate keys across Bots |
| Turn detection source | `bot-config` / Select Turn Detection source; `voice-pipeline` / Normalized ASR turn contract |
| Deepgram Flux/Nova-3 Model + Advanced | `bot-config` / Preserve current Deepgram advanced controls; Configure Deepgram Nova-3 |
| Speechmatics Advanced | `bot-config` / Configure Speechmatics enhanced with native settings |
| Soniox Advanced | `bot-config` / Configure language behavior, endpoint detection and context object |
| Speechmatics/Soniox compact refresh action | `bot-config` / Refresh an account-filtered catalog |
| AssemblyAI Advanced | `bot-config` / Configure U3.5 recognition, native turn, context and Voice Focus; `voice-pipeline` / AssemblyAI conversation context |
| Turn controls | `voice-pipeline` / Normalized ASR turn contract |
| Responsive drawer | `bot-config` / ASR drawer prototype conformance |

## Baseline governance

- D-019/D-020 amend the D-015 baseline only for the compact account-Catalog refresh action and Soniox/AssemblyAI language-label readability; the checksum above is the sole active baseline.
- Any intentional baseline change must update the Change, record the reason and obtain renewed user confirmation before replacing this checksum.
- Ordinary verification must never overwrite the confirmed baseline.
