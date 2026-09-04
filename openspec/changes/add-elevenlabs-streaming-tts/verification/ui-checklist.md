# UI Verification Checklist

- [ ] Entry remains inside the existing Bot editor; no new navigation page is introduced.
- [ ] Deepgram and LLM keys always appear; ElevenLabs key appears only for ElevenLabs TTS.
- [ ] Provider switching updates provider-specific voice source and credential fields.
- [ ] Voice Picker covers selection, preview, search, dynamic filters, loading, empty/error states, and pagination.
- [ ] ElevenLabs filter values come from returned metadata; missing values use `Unspecified`.
- [ ] Manual Voice ID remains available when ElevenLabs discovery fails.
- [ ] Saved selection is restored by stable Voice ID.
- [ ] Desktop and narrow viewport layouts remain usable.
- [ ] Existing latency fields and labels remain provider-neutral.
- [ ] Final implementation screenshots are attached before product acceptance.
