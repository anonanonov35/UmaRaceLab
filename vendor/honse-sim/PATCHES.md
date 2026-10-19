# Local amendments to honse-sim 0.13.0

Upstream pin and download URL: ORIGIN.json. Original license: LICENSE (GPL-3.0-only). All included WASM source is under source/; this is public community code, not decompiled game code.

Amendments:

- 1–18 runners; installed metadata timestep 0.066600002348423 s; matching rushed cadence and event-tick conversion.
- Elapsed timer begins at zero; actual normalized HP is exposed through collectors and WASM.
- Passive Vision/type 8 contributes to visible-distance lane decisions.
- Persistent rank history, phase/corner-specific overtake counts, usage 11 scaling, and sustained-rank history.
- Both alternatives retained with priority and shared cooldown; runtime preconditions latch only when observed.
- Dynamic duration and additional-activation DTO/runtime state; local HP/distance tables supplied by the Python adapter.
- Up to four all-corner candidate triggers for short cooldown, repeated activation IDs in event logs.
- Condition parser audit exposed to Python; unmapped effects are rejected by the application boundary.
- Real course/world transform and previous-frame distance-ratio correction for cornering/lane movement, using the user-supplied coordinate/quaternion samples.
- Continuous proximity/blocking timers, nearest-ranked neighbor selection, actual popularity, and ascending skill-ID evaluation.
- Regression tests and updated contract tests for the expanded field/vision behavior.
- Sub-tick finish crossing from actual course advancement (including lane cost); same-tick finish notifications sorted by crossing time, then runner ID for an exact tie. Eliminates tick-end quantization and gate-order bias in photo finishes. Native interpolation and exact-tie semantics remain unverified.

Build on the current Windows setup: tools/build_engine.ps1 at the project root. Rust 1.97.0 GNU + wasm32-unknown-unknown and wasm-bindgen CLI 0.2.127 are isolated in .local/. An ASCII-only temporary toolchain/target path avoids GNU linker path problems with Cyrillic workspace names. No source-replacement script is needed: source/ already contains the amendments.

Core verification: cargo test --manifest-path vendor/honse-sim/source/Cargo.toml -p honse-sim --lib. Integration fixtures from upstream were not copied; the command intentionally runs library unit tests. Numerical/native-game equivalence remains unverified.

Release packaging remaps compiler source paths with rustc's `--remap-path-prefix` in tools/build_engine.ps1 so the WASM contains no developer profile paths. This changes build metadata/panic source labels, not race mechanics. A fixed-seed Kyoto trace (frames, events and finish times) matched exactly before and after this rebuild. The original build has no native-game equivalence claim.
