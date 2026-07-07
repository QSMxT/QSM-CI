# In-vivo track data — *deferred (scaffold only)*

The **in-vivo** track will score reconstructions of real acquired data. Because there is no perfect
ground truth in vivo, scoring uses a **reference** and the subset of metrics that are meaningful
without a known chi map (correlation, XSIM, region statistics); phantom-only metrics
(calcification, DGM linearity) are reported as `null`.

## Open decision before this track goes live

Pick the reference:

- **COSMOS** — multi-orientation reconstruction as the pseudo-ground-truth. Strongest, but requires
  a multi-orientation acquisition.
- **Designated reference recon** — a fixed, agreed reconstruction (e.g. a published pipeline) that
  all submissions are compared against. Easier, but the "truth" is itself a reconstruction.

Until this is decided, `public/` is intentionally empty and `evaluate.yml` only runs the `sim`
track.
