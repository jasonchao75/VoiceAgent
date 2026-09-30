# Mobile WebRTC Demo Sharing UI Annotations

## Admin Share

- Risk: high
- Baseline viewports: 1440×900 desktop; 1024×768 compact desktop; 390×844 narrow
- Theme/locale: VoiceAgent dark theme; English; UTC fixtures
- Strict regions: product rail, Bot sidebar, topbar/tabs, public profile editor, publish status/action, Share card hierarchy, QR/link actions, status semantics
- Adaptive regions: two cards collapse to one column; link field/button stack below 420px
- Dynamic masks: public_id/link text, Bot name, timestamps

| Region | Size/layout | Typography | Color/border/radius | States | Delta Scenario |
|---|---|---|---|---|---|
| Top navigation | Existing fixed rail/sidebar + 52px topbar + 42px tabs | Existing platform scale | Existing VoiceAgent variables | Share active | View current navigation scope |
| Public profile | Full-width card above QR/link; two columns then one | 11px labels/body | Existing dark fields and green publish action | published/unpublished changes/not published | Explicit public profile and immutable publication snapshot |
| QR card | Desktop left column; centered square | 14px heading, 11px body | Light QR surface in dark card, 12/18px radii | Active/disabled/unpublished | Publish; Disable and re-enable |
| Web Link card | Desktop right column; min-width 0 | 11px field/button | Green secondary action; danger disable | Active/disabled/unpublished | Stable single-Bot demo link |
| Narrow layout | One column, no horizontal overflow | Text wraps | Cards retain borders/radii | All | Responsive layout |

## Mobile Call

- Risk: high
- Baseline viewports: 320×700, 375×812, 390×844, 430×932 and desktop review frame
- Theme/locale: VoiceAgent dark theme; English
- Strict regions: Ready CTA/privacy disclosure, state orb, status text, recent transcript, bottom controls, Transcript drawer
- Adaptive regions: orb/card spacing and text wrapping by height/width
- Dynamic masks: timer, transcript contents, Bot public title/description, network state

| Region | Size/layout | Typography | Color/border/radius | States | Delta Scenario |
|---|---|---|---|---|---|
| Ready CTA | Full-width 54px button near safe area | High-weight CTA | Accent green, 15px radius | ready/processing/disabled | Open active link; Grant permission |
| State orb | 132–178px depending height | 11px uppercase status | Accent rings, motion + text | listening/thinking/speaking/reconnecting | Mobile live-call experience |
| Recent conversation | 4 messages, max 168px, older messages progressively faded | 8px speaker + 10.5/12px text | Dark panel, 15px radius | confirmed/interim/hidden | Transcript scenario |
| Transcript entry | 36px visible pill; top icon 44px | 10px label | Green outline/soft background | default/focus | Open Transcript drawer |
| Call controls | Three equal columns; 54px visible circles and ≥44px targets | 9px labels | neutral/accent/danger | muted/captions/end | Toggle mute/captions/end |
| Transcript drawer | Bottom sheet, max 78%, vertical scroll only | 12px message text | differentiated Agent/You bubbles | open/closed/long text | Open Transcript drawer |
