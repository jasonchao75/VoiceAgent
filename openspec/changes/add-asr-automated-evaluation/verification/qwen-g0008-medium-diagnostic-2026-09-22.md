# Qwen G0008 medium diagnostic — 2026-09-22

## Authorization

- Decision: PD-062
- Recipient: Alibaba Cloud DashScope native API, `qwen3.8-max`
- Data scope: the two text-only Cases already sent by production Pass 2 group `G0008-46872a0431ac`; no audio, credentials, unrelated groups, or other batches
- Limit: at most three calls and USD 5 total
- Stop rule: call the original group once; split into two single-Case calls only if the original timed out or returned an invalid/incomplete structure

## Execution

- Reconstructed request estimate: 60,894 conservative UTF-8-byte units, exactly matching the frozen production group
- Parameters: Thinking enabled, `reasoning_effort=medium`, `max_completion_tokens=32768`, 300-second client timeout, JSON-object response
- Calls made: 1
- HTTP result: 200
- End-to-end latency: 223,373 ms
- Validated Cases: 2 of 2; response passed the production group and Case schema/ID checks
- Provider usage: 20,529 input tokens, 5,199 reasoning tokens, 5,713 visible output tokens, 10,912 total output tokens
- Estimated charge from the frozen price snapshot: USD 0.031441
- Response content was not printed or retained; SHA-256: `2be71476048acbe5d41c30ebc7b2f9edf00d90c2fdfd7ec10d592feb610e923d`
- Split fallback: not executed because the original group succeeded

## Conclusion

Lowering Qwen3.8-Max from its implicit `xhigh` default to `medium` materially bounds reasoning usage, but it does not make this real two-Case request finish within 120 seconds. The request completed correctly after 223.4 seconds, so the production failure is not a context-window overflow and cannot be fixed by reasoning effort alone. A Qwen-specific timeout above the observed latency is required in addition to explicit `medium`; timeout/structure-triggered splitting remains necessary as recovery but is still unverified externally because this parent request succeeded.

## Production immutability check

After the diagnostic, `G0008-46872a0431ac` remained `failed`, attempts remained `3`, its persisted error remained `timeout`, and the batch remained `partially_failed / pass_2 / 75%` at USD 0.5455426873611111. The diagnostic did not write its successful result or charge into the production batch.
