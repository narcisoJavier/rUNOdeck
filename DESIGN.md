# rUNOdeck Design Direction

## Design Read
Reading this as: a hardware companion desktop utility for an Arduino macro controller, in a high-contrast Swiss-Apple monochrome aesthetic (inspired by the World Time reference UI), dial `ENERGY 2 / RHYTHM 2 / MOTION 1`.

## Three Dials
- **ENERGY: 2 (Balanced)** — High-contrast monochrome surfaces and oversized tabular typography create immediate visual authority without decorative gradients or neon clutter.
- **RHYTHM: 2 (Consistent with purposeful breaks)** — Asymmetric split between the tactile 4x4 hardware matrix and the editorial inspector sheet, paired with full-width list rows for audio endpoints and combos.
- **MOTION: 1 (Hover and active hardware states only)** — Crisp 140ms state transitions on press and selection; zero endless loops or pulsing dots.

## Palette & Themes
Both Light (Reference Default) and Dark (rUNOdeck Logo Navy) themes are shipped and fully supported via the top-right `Light | Dark` pill switch.

### Light Theme (Reference Primary)
- **Canvas Background**: `#E6E6E2` (Warm stone outer frame)
- **Surface Primary**: `#F2F2F0` (Matte alabaster card surface)
- **Surface Card (Inactive)**: `#EFEFED` with `1px solid #DCDCD7` border
- **Surface Card (Active / Selected)**: `#0E0E10` (Stark ink black focal inversion) with `#FFFFFF` text
- **Text Primary**: `#111113` (Contrast on `#F2F2F0` is 16.4:1, exceeding WCAG AAA)
- **Text Secondary**: `#5C5C58` (Contrast on `#F2F2F0` is 5.8:1, exceeding WCAG AA 4.5:1)
- **Accent Indicator**: `#D97706` (Warm amber active indicator dot from reference UI)

### Dark Theme (Hardware Companion)
- **Canvas Background**: `#111318` (Deep slate from the rUNOdeck icon)
- **Surface Primary**: `#1A1D24`
- **Surface Card (Inactive)**: `#22262F` with `1px solid #323744` border
- **Surface Card (Active / Selected)**: `#F2F2F0` (Inverted alabaster focal card) with `#0E0E10` text
- **Text Primary**: `#F5F5F3` (Contrast on `#1A1D24` is 15.2:1)
- **Text Secondary**: `#9CA3AF` (Contrast on `#1A1D24` is 6.1:1)
- **Accent Indicator**: `#38BDF8` (Cyan accent matching the rUNOdeck infinity mark)

## Written Reasons for Major Visual Decisions (R-31)
- **Color (Stark Ink-on-Alabaster Inversion)**: Selected keys and active audio outputs invert to solid `#0E0E10` against `#F2F2F0` so the user can spot the active hardware binding at a glance without relying on glow or multi-color badges.
- **Layout (Split Hardware Matrix + Editorial Inspector)**: Places the 4x4 physical button topology beside an oversized typographic inspector so users see both spatial key position and exact command details simultaneously.
- **Typography (System Sans + Oversized Tabular Display Numerals)**: Uses `-apple-system, "Segoe UI Variable Display", sans-serif` with `tabular-nums` so key indices, coordinates, and shortcut labels align with instrument-grade precision.
- **Spacing (8pt Structural Grid with Generous Card Padding)**: Uses `20px` card padding and `12px` grid gaps to clearly separate the 16 tactile keys while preserving 44px+ hit targets.
- **Cards (Bordered Matte Rows & Squircle Key Caps)**: Key caps use `16px` radius to mirror physical key switches, while audio/combo rows use horizontal list cards matching the World Time reference cards.
- **Navigation (Circular Dock + Top Pill Switch)**: Uses the reference UI's circular dock buttons for view switching and the top-right `Light | Dark` two-state pill switch for appearance control.
