# Uma Race Lab UI 0.3

## Direction and audit

Visual overhaul of the existing Python/Tk desktop application. The user's `desktop-full (3).png` provides the reference: graphite navigation, near-white surfaces, orange emphasis, sharp geometry and bold sans-serif typography. The race, build editor and accuracy sections retain their responsibilities and navigation order.

The previous UI used green-tinted surfaces, green accents, default notebook tabs and numerous enclosing frames. Longer translations and short windows could squeeze the course diagrams and hide editor actions. The redesign removes redundant frames, adds clear navigation, highlights the winning row and reserves room for saving a build.

Skills applied: ui-ux-pro-max for product controls, layout, keyboard behavior and contrast; design-taste-frontend for reference interpretation, visual hierarchy and palette discipline. Its marketing-page rules are outside the scope of the simulator's data tables. This is a native Tk theme, not an implementation of a web design-system package.

The ui-ux-pro-max design-system search returned a suitable Minimalism & Swiss Style direction, but its landing-page structure and serif pairing did not fit this desktop tool. A narrowed style-domain search confirmed the same style for professional tools. Those recommendations are adapted to the supplied reference and existing stack.

Design dials: DESIGN_VARIANCE 6, MOTION_INTENSITY 2, VISUAL_DENSITY 7. Motion is limited to functional race replay and native hover/press feedback. There are no automatic decorative animations.

## Tokens

Source of truth: `uma_lab/theme.py`. Light and dark palettes have the same semantic roles; each window receives its own copy.

| Role | Light | Dark |
|---|---|---|
| Background | #f3f3f1 | #18191a |
| Surface | #fdfdfc | #222426 |
| Main text | #202020 | #f1f1ec |
| Secondary text | #626262 | #b3b3ad |
| Masthead | #1d1d1e | #151617 |
| Masthead text | #f4f4f1 | #f4f4f1 |
| Orange accent | #ff663d | #ff663d |
| Text on orange | #202020 | #202020 |
| Selection | #fbd8c9 | #5a3527 |
| Input boundary | #8a8a85 | #777972 |

Segoe UI supplies the Latin/Cyrillic type family with the installed Windows font. Headings use the same family's bold weight. Controls use a consistent sharp corner treatment and 4/8-based spacing. Main text, secondary text, masthead text and primary button text are checked against their backgrounds at 4.5:1 minimum. Entry focus uses a dark border; navigation and language buttons retain native keyboard focus outlines.

Charts use gray and orange phase markings with explicit names and distance labels. Participant colors remain data encodings with gate numbers, separate from the single UI accent.

## Layout

The default desktop size remains 1320x960, bounded by the actual screen. At heights below 850 the masthead contracts, supplementary prose is hidden and the results table shows fewer rows with scrolling. Both real course diagrams remain available. Editor actions are packed from the bottom before expandable skill lists so saving is always visible. The supported minimum remains 1100x780.

Main navigation is keyboard reachable, and Ctrl+Tab also changes sections. Dialogs support Escape; parameter dialogs provide explicit Cancel and Apply buttons. Loading disables simulation and replay controls and changes the action label. Errors and empty results have explicit text.

## Localization contract

`uma_lab/i18n.py` and `uma_lab/locales/en.json` provide per-window RU/EN UI translation, including controls, options, course labels, diagrams, model notes, skill statuses, result explanations and known application errors. Game-provided skill names/descriptions, character names, user-authored build names and exported simulation data keep their original text and identifiers. Native operating-system dialog buttons follow the Windows language.

Language is stored in `local/settings.json`, preserving the database path and unknown settings. A switch preserves raw form edits (including invalid in-progress numbers), selected character, active build, course, condition IDs, seed, playback speed/position, calculated race and diagnostic columns. It never validates or autosaves a build. A pending simulation keeps its original numerical inputs. Modal dialogs must be closed before changing the main-window language.

The application is 0.4.1; the core physics model remains `contested-local-0.2.2`. The input adapter now chooses grades from the full aptitude table for the course and strategy.

## Dark theme

The theme button beside RU/EN switches light and dark modes. `theme` is saved alongside `language` in settings.json. The same preference-switch path preserves raw edits, race data, playback, selected skills, scroll positions and the results/events divider. Switching either setting preserves the other, including during a pending calculation. Opening a modal temporarily prevents main-window preference changes.

The dark palette covers native Tk lists and text, ttk tables and field states, combobox popups, the editor, our own dialogs, chart backgrounds, elevation fills, phase lines and numbered runner markers. Accent buttons keep dark text in both modes. Chart markers use lighter fills with dark numbers at night. System file/message dialogs and window decorations continue to follow Windows settings; no operating-system theme is changed.

## Verification

- 60 Python tests, including card/rarity/unique links, legacy build loading, full aptitude routing, release privacy checks and runtime paths, catalog placeholder parity, language isolation, dynamic messages, palette isolation and contrast in both themes.
- `tools/smoke_ui_localization.py` exercises the installed game through our application using a copy of saved builds. Requires the local game and `local/autosave-builds.json`.
- RU and EN screens, skill library, conditions and advanced parameters were scanned for untranslated application text. Both languages were visually inspected at normal and compact desktop sizes.
- Switching with invalid unsaved input and during a controlled pending calculation preserved the race and numeric inputs. Language survived reopening. Original build-file and master.mdb hashes were unchanged.
- Screenshots and smoke output are private artifacts under ignored `local/`; no extracted game resources are committed.
- `tools/smoke_ui_theme.py` checks light/dark switching, RU/EN combinations, the combobox popup palette, preserved form/race state, theme changes during a pending simulation and restored preferences after reopening. Both themes were visually reviewed, including the compact layout and dark skill library. Report: local/ui-theme-031-report.json.

## Build editor 0.4

The user's game screenshots define the editor's information order: build name and a specific outfit version, five manually entered stats in one row, a surface/distance/style aptitude matrix, and a two-column skill list. The costume selector lists character names first and keeps variants together. Star rarity selects the correct source skill set; unique level is separate. The editor reads game relationships rather than deriving skill IDs from character IDs. It does not automatically add the card's optional learnable skills.

The selected version's own unique is attached and marked with text, including its level. Other full uniques cannot be added; their inherited entries remain available. Changing version replaces the attached unique and base aptitudes while preserving raw stat input. Adding a different tier in an existing skill group replaces that group's earlier tier. Duplicate builds have independent skill lists and aptitude dictionaries.

Skill cards use source rarity: pastel green/cyan/lilac/pink for uniques, pale yellow/amber for gold, white for normal/inherited skills. These light surfaces are intentional in both themes, following the screenshots; they use dedicated dark text tokens. Contrast checks cover every gradient stop for primary and secondary text. Type labels and the attached marker communicate meaning without relying on color. Gradients are drawn by Tk Canvas; no game assets are extracted or distributed.

Cards support click selection, arrow keys, Home/End, Enter/Space for details, and a separate Details button. The form can scroll independently at small desktop sizes; keyboard focus brings the current field into view. Saving actions and at least one row of skill cards remain available. Preference changes preserve all ten grades, unfinished numerical input, card selection and the form's scroll position. Destroyed Tk widget cycles are finalized on the UI thread before starting background work.

`tools/smoke_ui_builder.py` uses a private copy of saved builds and the local installed database. It checks all 111 variants / 352 rarity profiles in the tested DB, both Oguri versions, King Halo's low/high star uniques, save/reload, protected own unique, foreign-unique rejection, full grades and the unique in a real simulation payload. Screenshots cover RU light/dark, EN at 1100x780, all three card types and the skill library. Original build and DB hashes remain unchanged. Report: local/ui-builder-040-report.json.
