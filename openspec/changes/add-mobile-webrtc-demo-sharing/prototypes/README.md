# Mobile WebRTC Demo Sharing Prototypes

Status: **Frozen User Gate 1 baseline — confirmed 2026-09-29**.

## Files

- `mobile-call.html`: public mobile call flow; use the review dock to switch Ready, Connecting, Live call, Weak network, Error and Ended.
- `admin-share.html`: authenticated Bot Share page; use the review dock to switch Active link, Link disabled and Bot not published.

## Frozen Baseline Identity

| File | Frozen SHA-256 | Product source |
|---|---|---|
| `mobile-call.html` | `4dfa2c9d85b1e821c76691972f1b67ac0c30201d284f6d82e13da0e820f0c4de` | “对的，就是这样。” + “原型确认，依赖选 A” |
| `admin-share.html` | `cf15954f60f53218e6b3d3d06b8ccc0cad6b2982730eff88f3a30fe1fcc01040` | “原型确认，依赖选 A” |

These are the only frozen Gate 1 hashes. Ordinary validation MUST NOT replace them. Any intentional prototype change requires a recorded reason and renewed product confirmation.

## Traceability

| Prototype area | Delta Requirement / Scenario | Status |
|---|---|---|
| Share top-level navigation and Bot context | `bot-config` / Componentized Bot editor / View current navigation scope | Confirmed candidate |
| Share Active QR/Web Link and actions | `bot-config` / Stable single-Bot demo link / Publish a Bot | Confirmed candidate |
| Share public title/description and Publish updates | `bot-config` / Explicit public profile and immutable publication snapshot | Confirmed baseline |
| Share unpublished-changes state | `bot-config` / Edit a published Bot without publishing updates | Confirmed baseline |
| Share Disabled state | `bot-config` / Disable and re-enable a link | Confirmed candidate |
| Share unpublished state | `bot-config` / Open Share for an unpublished Bot | Confirmed candidate |
| Mobile Ready and unavailable | `mobile-web-call` / Public mobile demo entry | Confirmed candidate |
| Permission and Connecting | `mobile-web-call` / Explicit microphone and connection flow | Confirmed candidate |
| Live state orb and controls | `mobile-web-call` / Mobile live-call experience | Confirmed candidate |
| Recent 4-message transcript and drawer | `mobile-web-call` / Open the Transcript drawer | Confirmed candidate |
| Weak network / Error / Ended | `mobile-web-call` / Mobile call termination and recovery | Confirmed candidate |
| 320px+ mobile behavior | `mobile-web-call` / Mobile responsive and accessible layout | Confirmed candidate |

Behavior, data, auth and error rules follow Delta Specs. After Gate 1, visual structure, hierarchy, states and interaction details follow the frozen prototypes; example copy/timer/transcripts remain fixtures and MUST NOT ship as live data.
