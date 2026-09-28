# ASR Drawer UI Annotations

- Risk: high
- Baseline viewport(s): desktop 1440×1000; narrow 390×844
- Font/theme/locale/timezone: system sans; dark; English UI; timezone independent
- Strict regions: product rail, top tabs, Pipeline cards, ASR drawer hierarchy, Provider switching
- Adaptive regions: drawer width, card/grid columns, help-copy wrapping, vertical scroll
- Dynamic masks: none; prototype contains no dynamic timestamps

| Region | Size/layout | Typography | Color/border/radius | States | Delta Scenario |
|---|---|---|---|---|---|
| App rail | 216 px desktop; hidden narrow | 16 px brand | dark canvas, 1 px divider | active VoiceAgent | Existing layout baseline |
| Pipeline | 3 equal cards desktop; 1 column compact | 10 px eyebrow, 16 px title | 14 px radius; active green border | ASR active | Select provider |
| ASR drawer | 420–520 px desktop; full width narrow | 20 px title | left divider; sticky header/footer | open | Prototype conformance |
| Provider selector | full-width dropdown | 12 px label, 14 px value | standard input border/radius | four current choices; extensible | Select provider |
| Base form | two columns where related; fields top-aligned and never stretched by sibling help text | 12 px labels | 9 px inputs; 41 px select height | enabled/read-only/error future | Catalog validation |
| Language control | full width; provider/model-specific | 12/11 px | select or searchable multi-select chip picker | Flux model-derived / Nova-3 BCP-47 / Speechmatics Pack Catalog / Soniox 60-language model Catalog / AssemblyAI steering | Catalog validation and provider/model language scenarios |
| Turn source | full width select + help text | 12/11 px | standard control | Provider native / Off; Off means VAD/fixed silence; capability-disabled state explains why | Select Turn Detection source |
| Context callout | full drawer width | 12/11 px | green info surface | AssemblyAI only | Context modes |
| Advanced | collapsible; grouped provider/model parameters | 12 px section | 12 px container | Provider states; Deepgram Flux/Nova branches; Off hides intelligent Turn fields but retains VAD/fixed-silence threshold | Provider-specific config and normalized Turn contract |
| Bot credential | full width after Advanced | current online 12/11 px labels/help | standard password input + switch | blank keeps this Bot's saved key; replace affects only this Bot | Optional encrypted key storage |
