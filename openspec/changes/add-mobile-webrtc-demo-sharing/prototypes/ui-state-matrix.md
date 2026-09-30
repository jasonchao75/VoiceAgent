# Mobile WebRTC Demo Sharing UI State Matrix

| Scenario ID | Page/region | Fixture | Data state | Interaction/error state | Viewport | Delta Scenario | Evidence |
|---|---|---|---|---|---|---|---|
| SHARE-01 | Share | published-active | published public copy + one valid link | idle | 1440×900 | Open Share for published Bot | candidate prototype |
| SHARE-01A | Share public profile | published-draft | edited public copy/config; previous revision live | unpublished changes | 1440×900 | Edit a published Bot without publishing updates | candidate prototype |
| SHARE-01B | Share public profile | first-publish | title initialized from Bot name; optional empty description | publish | 1440×900 | Prepare the first public profile | candidate prototype |
| SHARE-02 | Share QR | published-active | long production URL | download/copy success | 1440×900 | Publish a Bot | candidate prototype |
| SHARE-03 | Share | published-disabled | same public_id | disabled | 1440×900 | Disable and re-enable | candidate prototype |
| SHARE-04 | Share | unpublished | editable public profile; no active public entry | unavailable link + publish available | 1440×900 | Open Share for unpublished Bot | candidate prototype |
| SHARE-05 | Share | credential-incomplete | saved Bot missing a key | blocked publish | 1440×900 | Open Share for unpublished Bot | implementation fixture required |
| SHARE-06 | Share | API-error | existing link | load/write failure | 1440×900 | Protect share management | implementation fixture required |
| SHARE-07 | Share | published-active | long title/link | narrow wrap | 390×844 | Responsive layout | candidate prototype |
| MOBILE-01 | Ready | active-link | normal public copy | idle | 390×844 | Open an active link | candidate prototype |
| MOBILE-02 | Ready | active-link | long public copy | no overflow | 320×700 | Narrow supported viewport | implementation fixture required |
| MOBILE-03 | Unavailable | disabled-link | safe public error | terminal | 390×844 | Open unavailable link | implementation fixture required |
| MOBILE-04 | Permission | active-link | mic prompt | requesting | 390×844 | Grant permission | candidate interaction |
| MOBILE-05 | Permission | active-link | denied/missing mic | recoverable error | 390×844 | Deny permission | implementation fixture required |
| MOBILE-06 | Connecting | session-created | pending ICE | processing | 390×844 | Grant permission | candidate prototype |
| MOBILE-07 | Connecting | expired/ICE failure | no media | retry | 390×844 | Initial connection fails | candidate Error + fixture required |
| MOBILE-08 | Live | opening/listening | real transcript | connected | 390×844 | Receive opening message | candidate prototype |
| MOBILE-09 | Live | thinking | recent 4 messages | connected | 390×844 | Mobile live-call experience | candidate prototype |
| MOBILE-10 | Live | speaking | recent 4 messages | barge-in | 390×844 | User interrupts Agent | candidate prototype + mock required |
| MOBILE-11 | Live | active | media track disabled | muted | 390×844 | Toggle mute | candidate interaction |
| MOBILE-12 | Live | active | transcript retained | captions hidden | 390×844 | Toggle captions | candidate interaction |
| MOBILE-13 | Transcript | long-conversation | 20+ turns/long words | drawer open | 320×700 | Open Transcript drawer | implementation fixture required |
| MOBILE-14 | Weak network | active session | ICE disconnected | reconnecting | 390×844 | Recover short interruption | candidate prototype |
| MOBILE-15 | Error | provider/network failure | safe category | retry | 390×844 | Call termination and recovery | candidate prototype |
| MOBILE-16 | Ended | completed call | duration/status | Call again/Done | 390×844 | End/Start another call | candidate prototype |
| MOBILE-17 | Ready | capacity-full | no lease | busy/retry | 390×844 | Public capacity is full | implementation fixture required |
