# Analytics (Google Analytics / Tag Manager)

Account and container used by the Beacon site (beacon.afrigen-d.org). IDs are public identifiers, not secrets. Sign-in is the AfriGen-D Google account; no credentials are stored here.

| Item | Value | Source |
|---|---|---|
| GA account | AfriGen-D, id `361190794` | GA admin URL |
| GA property "Beacon" | id `564501451` (data stream admin) | GA admin URL, 2026-11-16 |
| Second property in the same account | id `507137453` (name not recorded; reports home) | link pasted by the owner, 2026-11-16 |
| GTM container | `GTM-NZ5LBJLV` | "Set up a Google tag" page |

Links:

- Beacon property data streams: `https://analytics.google.com/analytics/web/#/a361190794p564501451/admin/streams/table/163532587`
- Second property reports home: `https://analytics.google.com/analytics/web/#/a361190794p507137453/reports/intelligenthome`

The FedImpute site uses its own GA4 measurement id (`G-C6SD0NN8ZX`, see the FedImpute repo); which property that id belongs to is not recorded here.

## Where the tag is loaded

- `frontend/src/app/layout.tsx` loads `GTM-NZ5LBJLV` on every page.
- `nginx/nginx-prod.conf` CSP allows `googletagmanager.com` and `google-analytics.com`. Correction (measured 2026-11-16): production does not use this file. The production nginx image bakes in `nginx-docker.conf`, which is not tracked in git and lives only on the node (`~/afrigend-beacon2/nginx/`); its CSP is `script-src 'self' 'unsafe-inline'`.
- The public responses of beacon.afrigen-d.org carry no Content-Security-Policy header today (the UCT front proxy does not pass it), so the CSP is not what decides whether the tag loads. If a CSP is ever enforced, it must allow `googletagmanager.com` and `google-analytics.com` in that baked config; the nginx image has not been rebuilt in 6 months.

## Privacy notes

- The home page puts the submitted variant (chr, start, alleles) in the URL query string. In GTM or GA4, set `page_location` to origin + pathname so it is not sent to Google.
- No consent banner is implemented. Decide whether POPIA/GDPR requires one before relying on the data.
