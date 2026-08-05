# Pre-rendered schema diagrams

Pre-rendered PNG / PDF / SVG of the diagrams in `../SCHEMA_DIAGRAMS.md`.
Use these for slides, papers, or contexts where Mermaid won't render.

| File stem | What it shows | Audience |
|---|---|---|
| `er-mongodb-literal` | 10 collections + indexes; `VariantInDataset` shown as a real join collection | DBAs, devs, ops |
| `er-domain-semantics` | Same data, collapsed into M:N entities (no join collection) | Researchers, papers, onboarding |
| `runtime-topology` | nginx → frontend / API → MongoDB / Redis | All |
| `api-endpoint-map` | Boolean vs Secure routes; stub-only routes flagged | Devs, integrators |
| `query-lifecycle` | Request flow: rate-limit → cache → Mongo → audit log | Devs, perf / ops |
| `deployment-topology` | Two ILIFU VMs + Cloudflare tunnel + UCT forwarder | Ops, infra |
| `tech-stack` | All technologies in use, grouped by layer (edge/FE/BE/data/infra/test/obs) | All — onboarding, RFPs, papers |

Each stem is available in three formats:

- `*.svg` — vector, infinitely scalable, edit in Inkscape / browser
- `*.png` — raster at 2× scale, drop into slides / Markdown
- `*.pdf` — vector for LaTeX / printing

## Re-rendering after edits

After editing `../SCHEMA_DIAGRAMS.md`, regenerate all three formats:

```bash
cd <repo-root>
npx --yes @mermaid-js/mermaid-cli -i docs/SCHEMA_DIAGRAMS.md \
  -o docs/diagrams/schema.svg --outputFormat svg
npx --yes @mermaid-js/mermaid-cli -i docs/SCHEMA_DIAGRAMS.md \
  -o docs/diagrams/schema.png --outputFormat png --scale 2
npx --yes @mermaid-js/mermaid-cli -i docs/SCHEMA_DIAGRAMS.md \
  -o docs/diagrams/schema.pdf --outputFormat pdf
```

Then rename `schema-1` … `schema-7` to the descriptive names above (the
mermaid-cli numbers them in document order; the order is the same as the
table-of-contents in `SCHEMA_DIAGRAMS.md`).
