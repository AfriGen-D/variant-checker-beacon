# Result cell and API call bar (mockup)

Published canvas: https://claude.ai/artifact/PphM8HwnuhcRVhHT2oQiCZ (private to the owner; version 6, 2026-11-17).

Requested 2026-11-17 after the user showed CRG's RNA-Get Beacon "Explore" page and asked what to copy. Three artboards at the real 1065px viewport, in this UI's own tokens (`design-system/foundations.html`):

- `Main.dc.html`: the four result-cell states (Present, Absent, Not covered, No/unchecked), each a word plus an icon plus a pattern, with the API condition behind each.
- `Grid.dc.html`: a variant x dataset grid, rows paged 5 at a time, one request per row.
- `AfGrid.dc.html`: the allele-frequency version of the grid: the value is the headline, bands (common 5% or more, low 1% to 5%, withheld below 1%, not reported), a bar per cell, and a stated reason for every missing number. Only the H3A V6 column is real ("AF not reported", the stored rs334 frequency is empty); every number is an example.
- `ApiBar.dc.html`: a persistent "API call" bar with the parameter table, the screen-to-API position conversion and a copy-curl button (interactive).

What is real and what is an example is stated on each artboard: only the H3A V6 column, rs334 and chr1:1,000,018 are real; the other two columns and the chrX and chr11:5,227,001 rows are examples.

Depends on the `coverage` block from PR 141 (`{chromosomes, alleleFrequency}`, key absent when unknown), which is live in v1.1.14 but not populated until `manage.py compute_coverage` is run on production. Until then the UI must show "No, unchecked", never "Not covered".

The `.dc.html` files are canvas sources (they load `support.js` from the design host), not standalone pages; the canvas link above is the way to view them. Not yet implemented: the React cell is `frontend/src/components/results/ResultCell.tsx` (PR 153); the bar and the grids are not built.
