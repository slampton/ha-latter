# Latter Studio design guide

This guide is the standard for Latter Studio, the admin panel in the Home Assistant sidebar (authored in modular TypeScript under `frontend_src/` on the zero-runtime-dependency `<template>`-marker Lit subset in `src/lib/lit.ts`, type-checked with mandatory `tsc --noEmit`, and bundled via Node 22 `stripTypeScriptTypes` in `frontend_src/build.mjs` into `custom_components/latter/frontend/latter-studio.js`). Read it before changing Studio. Every change to Studio follows it. The parts that can be checked automatically are enforced by the project's verification checks, named in brackets below (for example `[STUDIO TOKENS]`).

The [decision log](#decision-log) at the end records the standing choices behind this guide.

---

## 1. Purpose and scope

Studio owns three things:

1. **Latter-only settings**: options that exist only in Latter, such as shared entities, remote control groups, BLE calibration, wallpapers, the Home dock, and each Device's Latter settings.
2. **Cross-device actions**: profiles, bulk controls, BLE calibration and adoption, backups.
3. **Health and status**: what a Device is doing now and what needs attention.

Raw per-entity controls stay on Home Assistant's device page. Studio shows only a curated set of a Device's entities, in context, and links to Home Assistant for the rest. Studio never duplicates a Home Assistant screen.

## 2. The "real feature" rule

Every control in Studio is wired end to end, or it doesn't ship.

- A control reads a real value and writes it through a real handler that has a real effect (a config entry, a subentry, `.storage/latter.site`, a service call, an entity of the bound Device, or a Protocol v3 payload).
- No placeholders, demo values, "coming soon" sections, or settings that are stored but never read.
- **Unknown renders as `—`.** Never show a made-up value ("Online", "Plugged In", "Connected", a hard-coded version) when the real value is unknown.
- A payload field the UI doesn't read is removed. A command the UI doesn't call is removed.
- If a feature can't be finished, it's removed from Studio until it can.

## 3. Design tokens

Studio matches Home Assistant's own settings pages. Every visual value comes from a token. Tokens are defined **once**, in the `:host` block at the top of `STUDIO_STYLES`, and each one reads a Home Assistant theme variable with a fallback. No other rule in the file contains a font size, a pixel spacing value, or a color literal (`[STUDIO TOKENS]`: zero allowed outside `:host`).

Markup carries no inline styles (`[STUDIO INLINE STYLES]`). The one exception is a data-driven custom property, set from data on the element that needs it (`style="--signal-pct: 62%"`, `el.style.setProperty("--swatch-color", color)`), and read by a class rule.

### Type scale

| Role | Size / weight | Token | HA variable (matches) |
| :--- | :--- | :--- | :--- |
| Toolbar and page title | 20 / 400 | `--studio-font-title` | `--ha-font-size-xl` (hass-subpage toolbar) |
| Card and dialog title | 24 / 400, tracking -0.012em, line height 1.2 | `--studio-font-card-title` | `--ha-card-header-font-size`, `--ha-font-size-2xl` (ha-card header) |
| Sub-section title | 14 / 500 | `--studio-font-body` | `--ha-font-size-m` |
| Body and row label | 14 / 400, line height 1.6 | `--studio-font-body` | `--ha-font-size-m`, `--ha-line-height-normal` |
| Secondary text | 12 / 400, `--secondary-text-color` | `--studio-font-secondary` | `--ha-font-size-s` (ha-settings-row description) |
| Caption (chips, table heads) | 12 / 500 | `--studio-font-caption` | `--ha-font-size-s` |

Two weights only: `--ha-font-weight-normal` (400) and `--ha-font-weight-medium` (500). Fonts come from `--ha-font-family-body` and, for code, `--ha-font-family-code`. No hard-coded font stacks: the fallback is `inherit`, so a theme's font always wins.

### Spacing

A 4 px grid: **4, 8, 12, 16, 20, 24** (`--studio-space-1` … `-4`, `--studio-space-card-top`, `--studio-space-5`, from `--ha-space-1` … `-6`).

| Use | Value | Matches |
| :--- | :--- | :--- |
| Page padding | 24 (16 on narrow screens) | HA config pages |
| Card header padding | 20 top, 16 sides; 16 to the content | ha-card header (`20 16 24`, content pulled up 8) |
| Card content padding | 16 | ha-card `.card-content` |
| Card actions padding | 8, top divider | ha-card `.card-actions` |
| Gap between cards | 16 | |
| Settings row | min height 56, 8 vertical, no divider (a divider between stacked rows on narrow cards) | ha-settings-row |
| Gap between controls | 8 | |

### Sizes and radii

| Element | Size | Radius | Matches |
| :--- | :--- | :--- | :--- |
| Card | border `--ha-card-border-width` (1) in `--ha-card-border-color` | `--ha-card-border-radius` → `--ha-border-radius-lg` (12) | ha-card |
| Button | 40 high (compact 32), 16 side padding (compact 12), 14 / 500 | `--ha-button-border-radius` → pill | ha-button (`m` and `s`) |
| Text field and select | 40 high, filled: `--ha-color-form-background`, 1 px `--ha-color-border-neutral-loud` underline, 2 px primary underline on focus | `--ha-border-radius-sm` (4) on top, square bottom | ha-input (material appearance) |
| Switch | 48 × 24 outlined track, 18 thumb | pill | ha-switch |
| Dialog | | `--ha-dialog-border-radius` → `--ha-border-radius-3xl` (24) | ha-dialog |
| Inner boxes (list blocks, logs, previews) | 1 px divider border | `--ha-border-radius-md` (8) | |
| Toolbar | `--header-height` (56), `--app-header-border-bottom` | | hass-subpage |

### Colors

Colors come only from Home Assistant theme variables:

- Surfaces: `--primary-background-color` (page), `--card-background-color` / `--ha-card-background` (cards, dialogs, select popups), `--secondary-background-color`, `--divider-color`; toolbar `--app-header-background-color`, `--app-header-text-color`, `--sidebar-icon-color`.
- Text: `--primary-text-color`, `--secondary-text-color`, `--disabled-text-color`.
- Accent: `--primary-color`; tints are `rgba(var(--rgb-primary-color), <alpha>)`, never a fixed blue.
- Buttons, as ha-button: accent (main action) `--ha-color-fill-primary-loud-resting` / `--ha-color-on-primary-loud`; filled (secondary) `--ha-color-fill-primary-normal-resting` / `--ha-color-on-primary-normal`; plain (text) `--ha-color-on-primary-normal` with a `--ha-color-fill-primary-quiet-resting` hover; danger `--ha-color-fill-danger-normal-resting` / `--ha-color-on-danger-normal`, and `--ha-color-fill-danger-loud-resting` for a confirmation.
- Switch, as ha-switch: off `--ha-color-fill-disabled-quiet-resting` track, `--ha-color-border-neutral-normal` border, `--ha-color-on-neutral-normal` thumb; on `--ha-color-fill-primary-normal-resting` track, `--ha-color-border-primary-loud` border, `--ha-color-on-primary-normal` thumb. The `--ha-switch-*` overrides win.
- Fields: `--ha-color-form-background` (hover `--ha-color-form-background-hover`), `--ha-color-border-neutral-loud`.
- Status: `--success-color`, `--warning-color`, `--error-color`, `--info-color`.

Each of these falls back to the older variable a theme may still set (`--input-fill-color`, `--input-idle-line-color`, `--primary-color`, …), then to a literal.

**Light and dark mode.** Studio sets `color-scheme` from Home Assistant's effective mode (`hass.themes.darkMode`, reflected as the host's `dark` attribute), so the browser draws native popups (select lists, file and color pickers, scrollbars) in the matching scheme. Select options also get the card background and the primary text color explicitly, because a theme's field fill can be translucent.

Literal colors appear only as token fallbacks inside `:host`. User data (a saved color swatch, a wallpaper thumbnail) is the only exception, and it's set from data, never written in CSS.

### Token block

```css
:host {
  --studio-font-family: var(--ha-font-family-body, inherit);
  --studio-font-code: var(--ha-font-family-code, monospace);
  --studio-font-title: var(--ha-font-size-xl, 20px);
  --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
  --studio-font-section: var(--ha-font-size-l, 16px);
  --studio-font-body: var(--ha-font-size-m, 14px);
  --studio-font-secondary: var(--ha-font-size-s, 12px);
  --studio-font-caption: var(--ha-font-size-s, 12px);
  --studio-weight-regular: var(--ha-font-weight-normal, 400);
  --studio-weight-medium: var(--ha-font-weight-medium, 500);
  --studio-line-height: var(--ha-line-height-normal, 1.6);
  --studio-space-1 … --studio-space-4: var(--ha-space-1 … -4);   /* 4, 8, 12, 16 */
  --studio-space-card-top: var(--ha-space-5, 20px);
  --studio-space-5: var(--ha-space-6, 24px);
  --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
  --studio-radius-control: var(--ha-border-radius-md, 8px);
  --studio-radius-field: var(--ha-border-radius-sm, 4px);
  --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
  --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
  --studio-control-height: var(--ha-button-height, 40px);
  --studio-control-height-compact: 32px;
  --studio-row-min-height: 56px;
  --studio-header-height: var(--header-height, 56px);
  /* Colors, each reading the HA variable with a fallback: */
  --studio-bg, --studio-surface, --studio-surface-alt, --studio-input-bg, --studio-popup-bg,
  --studio-header-bg, --studio-header-text, --studio-header-icon, --studio-header-border,
  --studio-field-bg, --studio-field-bg-hover, --studio-field-line,
  --studio-divider, --studio-card-border, --studio-card-border-width,
  --studio-text, --studio-text-secondary, --studio-text-disabled,
  --studio-primary, --studio-primary-tint, --studio-primary-tint-strong,
  --studio-btn-accent-*, --studio-btn-tonal-*, --studio-btn-plain-hover, --studio-danger-tonal-*, --studio-danger-loud-*,
  --studio-switch-track, --studio-switch-border, --studio-switch-thumb, --studio-switch-on-*,
  --studio-success, --studio-warning, --studio-error, --studio-info (+ -tint),
  --studio-toast-bg, --studio-toast-text, --studio-scrollbar-thumb;
  color-scheme: light;   /* :host([dark]) { color-scheme: dark; } */
}
```

The `:host` block holds only declarations (no nested rules and no `}` inside comments), so the check can find where it ends.

## 4. Components

Studio has one implementation of each component. A new pattern is added here first, then built once and reused.

- **Card**: header (title and actions on the right) → content → optional footer actions separated by a divider, built by `renderCard()` (`src/components/controls.ts`). A card carries a one-line `.card-subtitle` only when it states a warning, consequence, prerequisite, or multi-Device / System blast radius that the title and controls don't show (D-012, D-024). A card that only lists the Device's own entities (marked `data-entity-card`, such as Sleep & Wake and Power & Battery) hides when the Device has none of them, as an empty group hides its title.
  ```html
  <div class="card">
    <div class="card-header">
      <div class="card-heading"><h3 class="card-title">…</h3><p class="card-subtitle">…</p></div>
      <div class="card-header-actions">…</div>
    </div>
    <div class="card-content">…</div>
    <div class="card-actions">…</div>
  </div>
  ```
- **Collapsible card**: a native `<details class="card">` whose `<summary>` is the card header. Used for long or advanced content (logs, raw entity inspector). Inside a card, a nested collapsible section uses `details.sub-collapsible`.
- **Settings row**: label and optional description on the left, the control on the right; no divider between rows (as ha-settings-row), except between rows stacked in a narrow card. Every Latter option and every curated Device setting goes through this one row, built by `renderSettingsRow()`, `renderSelectRow()`, and `renderSwitchRow()` (`src/components/controls.ts`): `.settings-list` > `.settings-row` > `.settings-row-text` (`.row-label`, `.row-description`) + `.settings-row-control`. `.settings-row.stacked` puts a wide control (a slider, a picker) under the label. Multi-slot entity lists (calendars, cameras, remotes) use `renderEntitySlotList()`.
- **Switch**: one style for every on/off setting, drawn like ha-switch (48 × 24 outlined track, 18 px thumb): `<input type="checkbox" class="switch" role="switch">`.
- **Text field and select**: Home Assistant's filled field: form background, 4 px top corners, a 1 px underline that becomes a 2 px primary line on focus. Native `<select>` keeps its own popup, drawn in Home Assistant's light or dark scheme.
- **Segmented control**: for a small either/or choice that changes the rest of a card (Notifications & Announcements: Notification or Announcement): `.segmented` with `role="radiogroup"` and `role="radio"` buttons using `aria-checked`.
- **Key/value rows**: `.kv-list` > `.kv-row` (label, value); unknown values show `—`. A row that opens something is a `button.kv-row`.
- **Lists**: `.list-row` (with `.list-row-main` and `.list-row-grow`) for short item lists with actions; `.list-block` for an item with a heading row (`.list-row-head`) and stacked fields (`.stacked-field`, `.field-label`).
- **Tables**: for lists longer than a few rows: `.table-wrap` > `table.data-table`. Sortable headers are `button.sort-btn` inside a `th` with `aria-sort`. Each row is focusable (`tabindex="0"`) and opens its item on click, Enter or Space.
- **Chips**: one shape, `.chip`, with variants `.chip-primary`, `.chip-success`, `.chip-warning`, `.chip-error` (no class is neutral). Status dots (`.status-dot`) use the same variants.
- **Empty state**: `<p class="empty-state">` renders a sentence that says what's missing and, where possible, how to add it. Never hidden, except inside an entity-only card, which hides as a whole.
- **Loading state**: `.loading-state`, shown until the first payload arrives; the page is never pre-filled with fake values. If the first load fails, an `.alert.alert-error` with a Retry button replaces it.
- **Error state**: every failed command shows an error toast (`.toast.error`) with the reason, from the one place that sends commands. A persistent problem (a Device health issue, a missing required entity) shows as an inline `.alert` (`.alert-warning`, `.alert-error`) in the card it affects.
- **Buttons**: pill-shaped like ha-button. `.btn` plus one variant: `.btn-primary` (accent: the main action), `.btn-secondary` (filled: a tonal primary fill), `.btn-text` (plain), `.btn-danger` (danger fill), `.btn-danger-filled` (loud danger, only inside a confirmation dialog). At most **one primary button per card** (D-009); the page header has no Save button (D-010). Two sizes: regular, and `.btn-compact` for buttons inside rows. Icon-only buttons are `.btn-icon` (`.btn-icon.danger` for delete) and always have an `aria-label`. Clustered one-tap Device actions at the top of Quick Actions use `.quick-action-grid` (`renderQuickActionGrid()`) with tonal `.btn.btn-secondary.quick-action-btn` tiles (icon + Title Case action name).
- **Dialogs**: a native `<dialog class="studio-dialog">`, synchronized with store modal state by `syncStudioDialogs()` (`src/components/dialogs.ts`). Esc closes it, focus moves into the dialog on open and returns to the opener on close. Confirmation dialogs say exactly what will happen.
- **Health**: Studio shows Latter's Home Assistant repairs and nothing else as health: a Device's repairs as one inline alert at the top of its Overview, and every Latter repair in the Issues card of the System's Overview. Both link to Home Assistant's Repairs page, where the repairs are fixed. Studio never computes a health warning of its own.
- **Accessibility**: every control has a visible label or an `aria-label`; scope and tab bars expose WAI-ARIA `role="tablist"` and `role="tab"` with `aria-selected` and roving arrow-key focus, and active navigation links set `aria-current="page"` (D-023); a set of toggle pills is a `role="group"` with a label; a pointer-only picker (the color wheel) always has a keyboard equivalent next to it (a native color input and a hex field); a segmented control is one tab stop and the arrow keys move between its options; text stays in the normal text color (a danger card or dialog shows danger with its border and its filled confirm button, not with red text, which fails contrast on dark themes).
- **View layout** (D-014): a view is `[wide cards] .columns > .column + .column [wide cards]`. Each `.column` is an independent stack, so cards flow top to bottom in their own column and a short card never leaves a gap beside a tall one. Below 760 px of content width the columns become one (the first column, then the second). Only a card with wide content (a log, a table, a gallery) spans the full width, and it goes first or last in the view. A view's cards are assigned to columns in the template; there is no auto-placing grid.
- **Narrow layouts**: cards are size containers; below 520 px of card width, settings rows and list rows stack (a container query, not a viewport media query), so a card in a narrow column behaves like a card on a phone, paired with `@media (max-width: 480px)` `.list-row` wrap rules so viewports down to 360 px wide never overflow horizontally (D-023).

## 5. Navigation

- Two scopes, selected at the top of the sidebar: **Devices** first and the default landing page (the Device list), **System** second (`[STUDIO DEFAULT VIEW]`).
- The URL follows the page, so reload and Back keep it:

  | URL | Page |
  | :--- | :--- |
  | `/latter` | Device list (the default) |
  | `/latter/devices/<subentry_id>` | That Device's Overview |
  | `/latter/devices/<subentry_id>/<page>` | `overview`, `display`, `interface`, `audio`, `power`, `presence`, `tools` |
  | `/latter/system/<page>` | `overview`, `shared`, `remotes`, `groups`, `presence`, `tools` |

  Studio writes the URL with `history.pushState` and a `location-changed` event, the way Home Assistant's own panels navigate. An unknown path—including a deleted or unknown `/latter/devices/<unknown_id>` route—redirects cleanly (`history.replaceState`) without firing commands for the missing Device (D-023).
- The **Visit** link on a Latter Device's Home Assistant device page opens that Device in Studio (`/latter/devices/<subentry_id>`).
- Studio's entry in Home Assistant's sidebar shows the Latter mark, `latter:logo` (D-017). Studio's own toolbar shows only the title, as Home Assistant's toolbars do.
- The page template starts in the Devices state, so nothing flashes before the first render.
- View names are unqualified, because the scope (Devices or System) is always shown; a name is qualified only if two views in the same scope would collide (D-018). The Device list is **All Devices**; Device pages use concise single-word labels—**Overview**, **Display**, **Interface**, **Audio**, **Power**, **Presence**, and **Tools**—while System pages are **Overview**, **Shared Entities**, **Media & Remotes**, **Device Groups**, **BLE & Area Presence**, and **Tools** (D-020, D-021, D-026). A nav label and its page title are the same text. A nav item carries a count badge only when the number is what its page lists (All Devices: the number of Devices).
- A Device's **Overview** holds what identifies it and what it's doing: one **Status** card (status, firmware, SDK revision, Area, battery, Wi-Fi signal, IP address, speaker, now playing, location mode, nearest BLE proxy, hardware model, ESPHome node name) whose footer links to **Open in ESPHome** (the ESPHome device page) and **Download Backup**, next to **Quick Actions** (quick actions, **Device Group** with its live group sync status and a **Reset to Group** action when customized, and assigned person). Uptime isn't shown: the firmware doesn't report it.
- One name per concept: **Device** (a Latter Device, with or without a screen; "display" on a Device means its panel brightness, theme and wallpapers, while **Interface** holds its on-screen Home, Dock, Activity Card, Area and Remote controls), **BLE Tag** (a tracked phone, watch or tag), **Remote Controls**, **Device Group** (each group carries its own operational behavior baseline), **Notification** (on-screen) and **Announcement** (spoken), **Settings** (never "options"), **Tools** (a scope's page for testers, backups, diagnostics and destructive actions).
- A Device's **Presence** page has **Area Tracking** (BLE Area tracking, switching the active Area on movement, the BLE presence beacon, fallback Area) and **BLE Identity** (BLE target, iBeacon UUID).
- A Device's **Tools** page has **Diagnostics** (the diagnostics file, network and status entities, a **Developer** group with the profiler, memory and weather simulation, and **All Entities**) in the first column, and **Perimeter Security Policy** (`security_pin_policy`: `auto` | `allow` | `require_pin` | `block` plus Device Security PIN configuration for unlocking locks, disarming alarms, and opening garage/gate/door covers), **Replace Hardware**, and **Danger Zone** (reset, remove) in the second (D-023). Settings that shape what the screen shows (such as Area cards per page and Remote Control Group assignment) live on **Interface**, while panel brightness, color profile and wallpapers live on **Display** (D-026).
- The System's **Tools** page has **Notifications & Announcements** (a tester) and **Backup & Restore** (export, restore, and **Rotate Signing Key** in one place), with **System & Device Logs** full width last. The shared **Custom Colors** library and **Wallpapers** gallery live on **System → Shared Entities**, while a Device's **Display** page has its **Custom Color** selector + **Add Color** button and per-Device **Wallpapers** activation, rotation, and uploads (D-022, D-023, D-026). Per-Device remote group assignments are edited on each Device's **Interface** page via `save_device_config`, while **System → Media & Remotes** displays a read-only **Device Assignments** status card with a **Configure** shortcut to each Device's **Interface** page (D-026).
- System pages work fully with no Device selected. A System action that acts on one Device names that Device in the action itself (a picker), never the "selected Device" of another page.

## 6. Content rules

- Use Home Assistant and IT terminology: **System**, **Sites**, **Areas**, **Devices**, **Roles**, **Policies**, **Bridges**. Never "household", "fleet", or "room" (`[STUDIO TERMINOLOGY]`).
- No marketing device names or personal equipment brands in labels or logic; Studio branches on hardware-manifest traits.
- **Titles and labels** use Title Case: every word capitalized, including each part of a hyphenated word, except a, an, the, and, or, of, to, in, on, for, with and &, unless first or last (D-013, `[STUDIO TITLE CASE]`). That covers page and nav names; card, section, sub-section and dialog titles; settings-row, key/value, field and switch labels; table headers; tabs and segmented options; and buttons. Body text, descriptions, placeholders, select options, chips, toasts and error messages stay in sentence case. Labels Studio builds from entity names (Home Assistant's, ESPHome's or the firmware's) go through one function, `entityLabel()`, which applies the same Title Case and keeps acronyms and brand casing (BLE, Wi-Fi, HA, IMU, SDK, ESPHome). Terminology words (System, Device, Area, …) and proper names (Home Assistant, Music Assistant, ESPHome, Voice Follows Me, Repairs) always keep their capitals. Help text is one short sentence that says what the setting does, not how it's built.
- Show entity IDs only where the user picks or inspects an entity.
- Units, numbers, and dates follow the user's Home Assistant settings (`hass.locale`, `hass.config.unit_system`). Times are relative ("2 min ago") where that reads better. Studio formats them with one set of helpers: `fmtNumber`, `fmtPercent`, `fmtDistance` (feet or metres by the unit system), `fmtAgo`, and `fmtDateTime` (the user's time zone setting, server or browser). The backend sends timestamps as UTC ISO 8601 and never formats them.

## 7. Engineering rules

- Studio is a `panel_custom` web component (`require_admin=True`, `embed_iframe=False`), authored in modular TypeScript (`frontend_src/src/**/*.ts`) on a zero-runtime-dependency `<template>`-marker Lit subset (`src/lib/lit.ts`), type-checked with mandatory `tsc --noEmit`, and bundled deterministically via Node 22 `module.stripTypeScriptTypes` (`frontend_src/build.mjs`) into `custom_components/latter/frontend/latter-studio.js` (verified in CI so HACS installs a ready-to-run bundle with zero Node requirement on Home Assistant). It exposes **zero `window.*` globals** and **zero inline `onclick="..."` string attributes**, and renders **only the active view** on each update (D-023, D-024).
- Studio talks to Home Assistant through admin-gated `websocket_api` commands (`latter/system/*` and `latter/device/*`), plus Bearer-authenticated multipart wallpaper uploads via `XMLHttpRequest` to `POST /api/latter/wallpaper/upload` (`hass.auth`, streaming up to 15 MB without hitting Home Assistant's 4 MB WebSocket frame limit; `fetch` is never called) (D-025).
- Every command the UI calls exists in the backend, and every backend command is used by the UI (`[STUDIO COMMANDS]`).
- `studio_rev` is validated on **both** read and mutation WebSocket commands (`ws_handle_system_command`, `ws_handle_device_command`), and `_studio_js_digest` is cleared on integration setup and unload (`studio/__init__.py`). When the backend reports `studio_rev_mismatch` after an integration update, Studio displays a dedicated **"Latter Studio was updated — Reload Page"** action banner (D-023).
- The websocket type is the scope: `latter/system/*` never acts on the selected Device (a System command that acts on one Device names it in its own payload), and `latter/device/*` acts on the Device named by its required `subentry_id`.
- The backend never acts on a client-chosen `entity_id` or `src` that it hasn't validated. Device entity actions are limited to the bound Device's own entities; bulk System actions are limited to the shared controls the backend itself offers; image URLs are minted and signed by the backend (including zero-device system wallpaper previews and **Rotate Signing Key**), and `POST /api/latter/wallpaper/upload` enforces Home Assistant's authenticated admin session (`requires_auth = True` + `hass_user.is_admin`).
- Every unauthenticated `GET` Latter HTTP view requires a scoped, expiring HMAC signature (`http.py`, 48 h day-bucketed TTL for Protocol v3 resource URLs and short exact expiry for on-demand streams), while `POST /api/latter/wallpaper/upload` requires an authenticated admin `Bearer` token (D-025). Studio never builds or signs a URL itself.
- No Home Assistant frontend internals: no `hass-subpage`, no walking other components' shadow roots, no `localStorage.hassTokens`, no `fetch` with stored tokens.
- Home Assistant's own pages (a device page, Repairs, the Latter integration, logs) open in the same tab with `openHaPage()` (the history API and a `location-changed` event, as Home Assistant's panels navigate), so Back returns to Studio. Studio never opens Home Assistant's dialogs or flows itself; it opens the page that has them. A download from a Home Assistant API (diagnostics) uses a short-lived path signed by Home Assistant's `auth/sign_path` command.
- Studio uses its own CSS rather than Home Assistant's internal `ha-*` elements (`ha-card`, `ha-switch`, …), which aren't a stable public API. It looks like them by using the same theme variables.
- The entity catalog (every entity offered in Studio's pickers) is the largest part of the payload, so only `get_state`, the first subscription answer and the first live push after an entity, device or Area registry change carry it; command answers and other pushes leave it out and Studio keeps the last one (`studio/settings.py`). Live BLE survey calibration streams incremental `ble_survey_delta` events over the existing WebSocket subscription (never `1.5 s` `get_state` polling), and `system_log` entries are sent only while the Logs view is open (D-023). A new payload field must earn its place: Studio renders it.
- Settings apply as they change (D-010) with **snapshot-isolated device switching** (D-023): each pending mutation captures `(scope, targetSubentryId, dirtyPatch)` at input time, so switching from Device A to Device B flushes pending edits strictly to Device A (`previousSubentryId`) before loading Device B, and reverts optimistic state cleanly on failure even if an input still holds focus. System settings and Device settings are written by separate commands with only the changed keys, and saving one never writes the other.
- Per-Device **Perimeter Security Policy** (`security_pin_policy`: `auto` | `allow` | `require_pin` | `block`, where `auto` resolves to `require_pin` on stationary panels or when a Home Assistant alarm code is configured, else `allow`) and optional PBKDF2-HMAC-SHA256 Device Security PINs are configured in Studio, pushed in Protocol v3 `area_context.security_pin_policy`, and enforced server-side (`protocol.py`) on opening actions (`unlock`, `unlock_door`, `disarm`, opening garage/gate/door covers) while closing/arming actions remain immediately accessible (D-023).
- A change to a Device entity (a select, switch or slider of the bound ESPHome device) shows at once: Studio applies the new state locally, so rows that depend on it appear or hide immediately, and keeps it over incoming payloads until the device reports it (at most 8 s); a failed command puts the old state back. The live subscription pushes when the Device's entities change state. Entity rows re-render from that state, wait while a select, text field or slider has focus (they render when focus leaves), and keep keyboard focus on the same control.
- Home Assistant's own Assist satellite selects for a Device (Assistant, Finished Speaking Detection, Wake Word, Wake Word 2) are recognized by their translation key and shown on **Audio** with Latter's voice settings. Home Assistant's Wake Word and Wake Word 2 are the one wake-word control; the firmware has no wake-word select of its own. With Wake Word Mode Disabled the wake words and their sensitivity hide; the assistant settings stay, because the action button, the Trigger Voice Assistant button and Home Assistant still start the assistant.

## Decision log

A standing decision stays in force until a new entry supersedes it. Changing one requires a new entry that names the entry it supersedes, explains why, and has the project maintainer's approval. Entries are never edited after they're accepted, except to set their status to "Superseded by D-xxx".

### D-001: Devices is the default view and the first tab
- **Date:** 2026-11-07
- **Decision:** Studio opens on the Device list. The scope switcher shows Devices first and System second.
- **Why:** Most visits are about one Device. System settings change rarely.
- **Alternatives:** System first (the previous layout); remember the last scope (rejected: reloads should be predictable).
- **Status:** Accepted.

### D-002: HA-aligned look, no distinct Studio look
- **Date:** 2026-11-07
- **Decision:** Studio looks like Home Assistant's own settings pages: same fonts, spacing rhythm, and theme colors. The long-term goal is that Studio could live natively inside Home Assistant.
- **Why:** Studio is an admin tool inside Home Assistant. A theme change in Home Assistant should change Studio too.
- **Alternatives:** A distinct Studio style (bigger headers, more whitespace, accent-colored section headers).
- **Status:** Accepted.

### D-003: The real-feature rule
- **Date:** 2026-11-07
- **Decision:** Every control is wired end to end or it doesn't ship; unknown values render as `—` ([section 2](#2-the-real-feature-rule)).
- **Why:** A control that does nothing, or a status that's made up, costs more trust than a missing feature.
- **Alternatives:** Ship placeholders behind "coming soon" labels.
- **Status:** Accepted.

### D-004: "People Tracked" means Devices with an assigned person
- **Date:** 2026-11-07
- **Decision:** The System overview counts Devices that have an assigned person, and the row opens the Device list filtered to them.
- **Why:** The old count was every `person.*` entity in Home Assistant, which says nothing about tracking.
- **Alternatives:** Remove the row.
- **Status:** Accepted.

### D-005: Uploaded wallpapers are private and served by signed URL
- **Date:** 2026-11-07
- **Decision:** Uploads are stored in Latter's private storage (`.storage/latter/wallpapers/<device>/`), never under `/config/www`. They're served only through the signed, expiring Latter wallpaper view. Existing uploads are moved there at startup, and stored references are updated.
- **Why:** Home Assistant serves `/config/www` at `/local/` without authentication. Every other Latter resource uses signed URLs.
- **Alternatives:** Keep `/config/www` (rejected: unauthenticated).
- **Status:** Accepted; moving existing uploads at startup superseded by D-019.

### D-006: Own CSS, not Home Assistant's internal `ha-*` elements
- **Date:** 2026-11-07
- **Decision:** Studio builds its components with its own CSS on Home Assistant theme variables.
- **Why:** `ha-*` elements aren't a public API; they may not be loaded and can change in any release.
- **Alternatives:** Use `ha-card`, `ha-switch`, `ha-select` directly.
- **Status:** Accepted.

### D-007: One Save per scope
- **Date:** 2026-11-07
- **Decision:** System settings are saved with a System command and Device settings with a Device command. One Save button may save whichever scopes have unsaved changes, but each scope is saved independently and saving one never writes the other.
- **Why:** System pages must work with no Device selected, and a Device save must not overwrite System settings.
- **Alternatives:** One combined save command (the previous design, which needed a selected Device).
- **Status:** Superseded by D-010.

### D-008: One media-handoff setting
- **Date:** 2026-11-07
- **Decision:** A Device has one setting for handing media to the Area it moves into, used for both BLE moves and on-device Area picks.
- **Why:** Two overlapping settings, one of them hidden, made the behavior impossible to predict.
- **Alternatives:** Show both settings with honest labels.
- **Status:** Accepted; implemented 2026-11-07 (the firmware's own switch is gone; the Latter setting `area_handoff` decides for both).

### D-009: One primary button per card
- **Date:** 2026-11-07
- **Decision:** The page header's Save is the view's primary button. A card may have one primary button of its own when its single action is the card's purpose (Download, Restore, Send Notification, Upload Photo, Capture Profile). Every other button in a card is secondary, text or icon.
- **Why:** The rule keeps the main action of each card obvious without turning a page of single-purpose cards into a page of secondary buttons.
- **Alternatives:** One primary button per view (the header Save only; every card action secondary).
- **Status:** Accepted.

### D-010: Every setting applies as it changes
- **Date:** 2026-11-07
- **Decision:** There is no Save button. A switch, select or slider applies when it changes (a slider when it's released); a text or number field commits on Enter or when it loses focus. Changes in quick succession are coalesced into one write of just the changed keys, per scope (System or Device), so a run of clicks doesn't flood Home Assistant or the device payload. A failed write shows the error toast and puts the control back to its saved value. Success toasts appear only when the result isn't visible on the page. System and Device settings are still written by separate commands and never write each other. Supersedes D-007; D-009's one-primary-per-card rule stands, minus its header Save.
- **Why:** It's how Home Assistant's own entity and settings controls behave, and a page that mixes "applies now" with "waits for Save" leaves the user guessing.
- **Alternatives:** Keep one Save button for everything (D-007); mark each card as "applies now" or "needs Save".
- **Status:** Accepted.

### D-011: Titles use Title Case
- **Date:** 2026-11-07
- **Decision:** Page and nav names, card titles, section and sub-section titles, and dialog titles capitalize every word except the minor words a, an, the, and, or, of, to, in, on, for, with and &, which stay lowercase unless they're first or last ("Location & BLE", "Announcements & Alerts", "Danger Zone", "Display & Home"). Buttons, row labels, options, help text and toasts stay in sentence case. latter-verify's `[STUDIO TITLE CASE]` check enforces it.
- **Why:** The maintainer's choice: titles read as names and stand apart from the controls under them.
- **Alternatives:** Sentence case for every label, as Home Assistant's own settings pages do (the previous content rule).
- **Status:** Superseded by D-013.

### D-012: No descriptive subtitles
- **Date:** 2026-11-07
- **Decision:** A title has no "what this section configures" line under it. A card keeps a description only when it carries something critical that the title and the controls don't show: a warning, a consequence or a prerequisite (for example "Not a full backup", "Up to 10 cameras", or how to calibrate). Row descriptions under individual settings are unaffected.
- **Why:** Descriptions that restate the controls add reading without adding information, and they hide the few lines that matter.
- **Alternatives:** A one-line description on every card (the previous card rule).
- **Status:** Accepted; partially superseded by D-024 (scoped `.card-subtitle` on System, multi-Device, security, and gallery cards).

### D-013: Titles and labels use Title Case
- **Date:** 2026-11-08
- **Decision:** Title Case extends from titles to every label: settings-row labels, key/value labels ("Latter Version", "Online Devices", "BLE Area Proxies"), Shared Entities labels ("Entry Lock", "Garage Door", "Robot Vacuum"), field and switch labels, table headers, tabs and segmented options, dialog titles, and buttons ("Add Device", "Open in Home Assistant"). The minor words stay as in D-011, and each part of a hyphenated word is capitalized ("BLE-Tracked Devices"). Body text, descriptions, placeholders, select options, chips, toasts and error messages stay in sentence case. `[STUDIO TITLE CASE]` checks every pattern it can match reliably. Supersedes D-011.
- **Why:** The maintainer's choice: one casing for everything that names a thing on the page, so a label never looks different from the title above it.
- **Alternatives:** Title Case for titles only (D-011).
- **Status:** Accepted.

### D-014: Two independent column stacks
- **Date:** 2026-11-08
- **Decision:** Every view lays its cards out in two independent column stacks (`.columns > .column`): cards flow top to bottom within their column, rows are never aligned across columns, so there are no gaps. Below 760 px of content width the two columns become one, first column first. Only cards with wide content (logs, tables, galleries) span the full width, placed first or last in the view. Cards are assigned to a column in the template.
- **Why:** The previous auto-fit grid aligned cards in rows, so a short card beside a tall one left a gap, and some views were one full-width column while others were two.
- **Alternatives:** CSS multi-column (`columns: 2`), which balances automatically but moves cards between columns as content opens and closes; a masonry grid (not yet available in every browser).
- **Status:** Accepted.

### D-015: Home Assistant's component metrics
- **Date:** 2026-11-08
- **Decision:** Studio's components copy the metrics and theme variables of Home Assistant's own components (frontend source, 2026.11): ha-card (24 px regular header, 20/16 padding, `--ha-card-*` border, radius and shadow), ha-settings-row (56 px rows without dividers), ha-input's filled field, ha-button (pill; accent, filled and plain), ha-switch (48 × 24 outlined track), the hass-subpage toolbar (56 px, 20 px regular title, `--app-header-*`), and Home Assistant's light or dark `color-scheme` for native popups. Studio still draws them with its own CSS (D-006); section 3 lists each value and the variable it reads. This carries out D-002.
- **Why:** The maintainer found the light theme usable but not like Home Assistant, and native select popups were unreadable in dark mode. Matching the real components, rather than approximating them, makes a theme change in Home Assistant look right in Studio too.
- **Alternatives:** Keep Studio's earlier compact metrics (16 px card titles, 36 px square-cornered controls, row dividers).
- **Status:** Accepted.

### D-017: The Latter mark is the sidebar icon, not a toolbar logo
- **Date:** 2026-11-08
- **Decision:** Studio's toolbar shows only the title "Latter". The Latter mark becomes Studio's icon in Home Assistant's sidebar: the panel registers with `sidebar_icon: "latter:logo"`, and a tiny frontend module, `frontend/latter-icons.js`, defines it through Home Assistant's custom icon API (`window.customIcons["latter"].getIcon(name) → {path, viewBox}`, frontend `src/data/custom_icons.ts`). The glyph is the mark's single 24 × 24 path with no color of its own, so it takes the sidebar's icon color and selected state like Home Assistant's icons. The module is served from Studio's static directory with a content-hash cache-buster (like the panel module), added with `frontend.add_extra_js_url`, and removed with `frontend.remove_extra_js_url` when the panel is removed. If the module can't be registered, the panel uses `mdi:ladder`.
- **Why:** The maintainer's choice: Home Assistant's toolbars carry no logo, and its sidebar is where an integration's mark belongs.
- **Limits:** Home Assistant loads extra modules early but asynchronously and has no fallback for an unknown icon set: if the module fails to load in the browser, the sidebar shows no icon (the title still shows). HACS has used the same mechanism for its sidebar icon for years.
- **Alternatives:** Keep the logo in the toolbar; use an MDI icon in the sidebar.
- **Status:** Accepted.

### D-018: View names are unqualified within their scope
- **Date:** 2026-11-08
- **Decision:** A view's name doesn't repeat its scope: the scope switcher already says Devices or System, so the System's views are **Overview** and **Settings** (not "System Overview" and "System Settings"), and a Device's settings view is **Settings** (not "Device Settings"). A name is qualified only when two views in the same scope would otherwise collide. The rule covers nav labels, page titles and links to a view; URL slugs were already unqualified.
- **Why:** The maintainer's choice: "System Overview" beside a Device's "Overview" read as two different kinds of page, and the System's overview holds more than system information.
- **Alternatives:** Qualify every name with its scope.
- **Status:** Accepted; the Settings view names superseded by D-020 (the naming rule stands).

### D-019: No migration code
- **Date:** 2026-11-08
- **Decision:** Latter reads only its current storage formats: no startup migrations, upgrade shims or aliases for earlier settings, uploads or backups. This supersedes D-005's move of existing uploads at startup; the rest of D-005 stands. A format change ships with the code that writes it, and nothing that reads the old one.
- **Why:** The maintainer's choice: Latter has no users on earlier formats before its public release, and every migration path is code that must be kept correct.
- **Alternatives:** Keep the one-time migrations until the public release.
- **Status:** Accepted.

### D-020: Tools pages, a Device presence page, identity on the Overview
- **Date:** 2026-11-08
- **Decision:** Both scopes end with a **Tools** page instead of **Settings** (`/system/tools`, `/devices/<id>/tools`; the old `settings` paths are gone, no redirects). System Tools holds Notifications & Announcements, Backup & Restore (Export Settings and Restore From File merged) and the logs; Device Tools holds Diagnostics (with the diagnostics file), Replace Hardware and the Danger Zone. A Device gets a **BLE & Area Presence** page (`/devices/<id>/presence`, the System page's name: one name per concept) with everything from the former Location & BLE card. A Device's identity moves to its **Overview**: the ESPHome node name in Status, Device Group in Quick Actions, and the Home Assistant device page as a Status footer link. The Custom Color Library moves to Groups & Profiles, beside the other resources shared across Devices. The Device pages' entity-count nav badge is removed: it counted entities, not what the page showed. This supersedes D-018's view names (Settings); D-014's two-column layout applies to every new page.
- **Why:** The maintainer's review: "Settings" pages had become a mix of identity, presence, testers, backups and destructive actions. Each item now sits where its purpose is, and a page's name says what's on it.
- **Alternatives:** Keep one Settings page per scope with more cards.
- **Status:** Accepted; Groups & Profiles and Custom Color Library placement superseded by D-021; Device view names and Display/Interface split superseded by D-026.

### D-021: Unified Device Groups with two-tier baselines and inline Custom Color Library
- **Date:** 2026-11-10
- **Decision:** Configuration Profiles, Device Groups, and Bulk Device Controls merge into one **Device Groups** page (`System → Device Groups`, `/latter/system/groups`, superseding `Groups & Profiles` in D-020). Standalone Configuration Profiles (`saved_profiles`, `capture_profile`, `delete_profile`, `apply_profile`) and the duplicate Sleep & Wake Power Profile dropdown on Device Overview Quick Actions are removed. Each Device Group (`unassigned`, `handhelds`, `wearables`, `bedrooms`, `common_areas`, `wall_panels`, plus custom groups) holds a stored **Tier 2 operational behavior baseline** (sleep & wake power profile and timeouts, brightness schedule, wake-word mode and sensitivities, alert volume, and BLE tracking / Voice Follows Me / media handoff). Assigning a Device to a group or clicking **Sync Group** / **Reset to Group** applies its Tier 2 operational baseline (`select:power_profile` first, skipping redundant sleep/wake calls that match `POWER_PROFILE_SPECS` so the firmware never falsely flips to `Custom`) while preserving **Tier 3 personal & Area appearance** settings (clock face, color profile, custom color, dock apps, activity card, wallpapers, Area category/page size, remote group, music screen style). Editing an operational control on **System → Device Groups** updates matching Devices live and saves the new value into the group's baseline; Tier 3 appearance controls sit in a collapsible bulk-override drawer. On **Device → Overview → Quick Actions**, **Device Group** is the single preset selector and shows a live `In Sync` or `Customized` chip with a **Reset to Group** button. The shared 24-swatch **Custom Color Library** moves inline into **Device → Display & Home → Display & Appearance** right where custom colors are chosen and managed.
- **Why:** Having Device Groups, Configuration Profiles, and Sleep & Wake Power Profile side by side on Overview—and separate Profiles vs. Bulk Controls cards on System—created three overlapping ways to apply presets and risked overwriting room-specific appearance (clock faces, wallpapers, dock apps) when syncing operational behavior.
- **Alternatives:** Keep standalone Configuration Profiles alongside Device Groups with category checkboxes on every apply action.
- **Status:** Accepted; Custom Color Library placement superseded by D-022.

### D-022: Shared Custom Colors and Wallpapers on System → Shared Entities, streamlined Device Custom Color selector and upload bar
- **Date:** 2026-11-10
- **Decision:** **System → Shared Entities** adds a **Custom Colors** card (in the second column) and a full-width **Wallpapers** gallery card (below `.columns`), and both are counted under **System → Overview → Configured Items**. Uploaded wallpapers are shared across the System and all Devices (`upload_system_wallpaper` / `delete_system_wallpaper` on System, `upload_wallpaper` / `delete_wallpaper` on any Device), alongside the 5 bundled photographic default presets (`preset:forest_mountains`, `preset:wheat_field`, `preset:ocean_waves`, `preset:sahara_dunes`, `preset:andromeda_galaxy`). On **Device → Display & Home**, the redundant `Add a color…` (`__new__`) option inside `#dev-custom-palette-select` and the collapsible `Saved Custom Colors` drawer are removed: `#dev-custom-palette-select` lists saved custom colors directly next to the **Add Color** button. In both wallpaper upload bars, `<input type="file">` uses intrinsic sizing (`flex: 0 1 auto`) so **Upload Photo** sits immediately beside **Choose File** and stays `disabled` until a file is chosen. Supersedes D-021's inline Custom Color Library placement on Device Display & Home.
- **Why:** Custom colors and uploaded wallpapers are shared System resources; users expect a global entry point under **System → Shared Entities** in addition to per-Device selection, and the Device Custom Color row had duplicate "add" triggers and a duplicate list of saved colors.
- **Alternatives:** Keep wallpapers per-device only and keep the Custom Color Library drawer only on Device Display & Home.
- **Status:** Accepted; base64 WebSocket wallpaper upload commands superseded by D-023 and removed in D-024; bundled preset count expanded to 6 in D-025.

### D-023: Modular TypeScript + Lit bundle, zero window globals, snapshot-isolated saves, `studio_rev` banner, signed multipart uploads, streaming BLE deltas and Perimeter Security Policy
- **Date:** 2026-11-10
- **Decision:** (1) Studio is authored in modular TypeScript + Lit under `ha-latter/frontend_src/` (`latter-studio.ts`, `state/`, `api/`, `components/`, `views/`, `styles/`) and bundled via `esbuild` into the committed `custom_components/latter/frontend/latter-studio.js`, eliminating all `window.*` globals and inline `onclick="..."` string attributes and rendering only the active view on each update. (2) Pending setting edits snapshot `(scope, targetSubentryId, dirtyPatch)` at input time so switching Devices flushes pending edits strictly to the originating Device (`previousSubentryId`) and reverts optimistic state on error even while an input retains focus. (3) `_studio_js_digest` resets on integration setup/unload, `studio_rev` is enforced on both read and write WebSocket commands, and `studio_rev_mismatch` displays a dedicated **"Latter Studio was updated — Reload Page"** banner. (4) Wallpaper uploads mint a short-lived signed upload URL over WebSocket and stream `multipart/form-data` (up to 15 MB) via `XMLHttpRequest` to `POST /api/latter/wallpaper/upload` (superseding base64 WebSocket upload frames in D-022 while keeping zero `fetch()` calls), zero-device system wallpaper previews sign cleanly, and **Rotate Signing Key** lets admins rotate the System HMAC key. (5) BLE calibration streams incremental `ble_survey_delta` events over the existing WebSocket subscription (retiring `1.5 s` `get_state` polling), `system_log` entries ship only while the Logs view is open, and unknown `/latter/devices/<unknown_id>` URLs redirect cleanly. (6) Scope and tab controls expose WAI-ARIA `role="tablist"` / `role="tab"` + `aria-selected` + roving arrow-key focus, active nav links expose `aria-current="page"`, and `@media (max-width: 480px)` `.list-row` wrap rules eliminate horizontal overflow at 360 px. (7) Per-Device **Perimeter Security Policy** (`security_pin_policy`: `auto` | `allow` | `require_pin` | `block`) and PBKDF2-HMAC-SHA256 Security PIN configuration ship in Studio, governing opening actions (`unlock`, `unlock_door`, `disarm`, opening garage/gate/door covers) in lockstep with the on-device `ui::pin_pad_modal`.
- **Why:** Eliminates global namespace pollution, cross-device save races, post-HACS-update `studio_rev` deadlocks, 4 MB WebSocket frame disconnects on high-res photos, hidden-view DOM churn, and `1.5 s` catalog polling while enforcing server-verified perimeter security.
- **Status:** Accepted; bundler architecture (`esbuild` / external `lit`) and monolithic `store.ts` superseded by D-024; signed upload URL mechanism in (4) superseded by D-025.

### D-024: Scoped `.card-subtitle` blast-radius rule, 4-module store split, declarative view helpers, and zero-dependency `stripTypeScriptTypes` + `tsc --noEmit` bundler
- **Date:** 2026-11-11
- **Decision:** (1) Partially supersedes D-012 for cards that act across multiple Devices, configure System-wide shared resources, or govern security policies and wallpaper galleries: those cards carry a concise one-line `<p class="card-subtitle">` clarifying blast radius, prerequisites, or slot limits (retiring the unused `.card-description` class), while routine single-Device cards stay subtitle-free. (2) Decomposes `frontend_src/src/state/store.ts` into 4 focused modules (`store.ts` core reactive controller, URL router, and WebSocket subscription; `entity-config-ops.ts` snapshot-isolated saves, entity overlays, dock/activity/palette/wallpaper/remote/doorbell ops; `groups-presence-ops.ts` Device Groups, bulk controls, BLE calibration, and Area fusion ops; `dialogs-tools-ops.ts` Security PIN, signing key rotation, diagnostics, modals, announcements, backup/restore, and timezone-aware `fmtDateTime` log formatting), and standardizes all 13 views on shared declarative helpers in `src/components/controls.ts` (`renderCard`, `renderSettingsRow`, `renderSelectRow`, `renderSwitchRow`, `renderEntitySlotList`). (3) Supersedes D-023's `esbuild` / external `lit` bundler description: Studio runs on the zero-runtime-dependency `<template>`-marker engine in `src/lib/lit.ts` (including boolean WAI-ARIA string serialization for `aria-checked`) and is built by `frontend_src/build.mjs` using mandatory `tsc --noEmit` type-checking plus Node 22 `module.stripTypeScriptTypes` with lexer-aware blank/type-hole compaction outside template literals. (4) Retires the unused `upload_system_wallpaper` and `upload_wallpaper` WebSocket command names left over from D-022 and purges all pre-Protocol-v3 payload fallback shims and orphan CSS/DOM classes.
- **Why:** Makes System-wide and multi-Device blast radius obvious at a glance without cluttering single-Device cards, keeps every state and view module compact and strictly type-checked with zero runtime npm dependencies, fails builds immediately on any TypeScript error, and eliminates dead shims and type-stripped whitespace holes from `latter-studio.js`.
- **Alternatives:** Remove all `.card-subtitle` lines on System and security cards (loses multi-Device blast-radius context); depend on external `esbuild` and `lit` npm packages at build/runtime.
- **Status:** Accepted.

### D-025: Bearer-authenticated multipart wallpaper uploads and 6 bundled photographic presets
- **Date:** 2026-11-12
- **Decision:** (1) Supersedes D-023 (4)'s WebSocket-signed upload URL mechanism for `POST /api/latter/wallpaper/upload`: `StudioWsClient.uploadWallpaperMultipart()` authenticates `XMLHttpRequest` `POST /api/latter/wallpaper/upload` directly with `Authorization: Bearer <access_token>` from Home Assistant's live in-memory `hass.auth` session (`refreshAccessToken()` when `hass.auth.expired` plus a single refresh-and-retry on `HTTP 401` for clock skew; never touching `localStorage` or `fetch()`), matching `LatterWallpaperUploadView` (`requires_auth = True` and `hass_user.is_admin`). `signHaPath` (`auth/sign_path`) stays strictly for `GET` endpoints (diagnostics downloads and camera previews). (2) Expands `BUILTIN_WALLPAPER_PRESETS` from 5 to 6 bundled `720×720` baseline JPEGs by adding `preset:mars_crater` ("Mars Crater", `mars_crater.jpg`), completing a balanced 3×2 gallery grid alongside the existing presets.
- **Why:** Home Assistant Core's `auth_middleware` (`homeassistant/components/http/auth.py`) honors `?authSig=` (`auth/sign_path`) exclusively on `GET` and `HEAD` requests, causing signed `POST` multipart uploads without a `Bearer` header to be rejected with `401 Unauthorized` before `LatterWallpaperUploadView.post()` ran.
- **Alternatives:** Set `requires_auth = False` on `LatterWallpaperUploadView` and mint a custom Latter HMAC upload token over WebSocket (adds a parallel auth path when Studio already runs inside an authenticated admin `panel_custom` with `hass.auth`).
- **Status:** Accepted.

### D-026: Single-word Device navigation, Display vs. Interface split, and per-Device Remote Control Group assignment
- **Date:** 2026-11-12
- **Decision:** (1) Simplifies Device view names (superseding D-020's multi-word Device labels while keeping System nav names unchanged) and splits the oversized 5-card `Display & Home` page into two focused `caps.has_display`-gated pages: **Display** (`/latter/devices/<id>/display`: Column 1 **Brightness & Theme** with Auto/Manual/Day/Night Brightness, schedule hours, Color Profile, Custom Color selector and **Add Color**; Column 2 **Wallpapers** with active status, rotation interval, favorites, presets and uploads) and **Interface** (`/latter/devices/<id>/interface`: Column 1 **Home Screen** with Start Screen, Clock Face, Time Format, Dock Apps, Wake Greeting, Weather Background and Sun & Moon pills plus **Activity Card**; Column 2 **Area Controls** plus **Remote Controls**). The full Device menu is **Overview**, **Display**, **Interface**, **Audio**, **Power**, **Presence**, and **Tools** (expanding Studio to 14 views total, 13 two-column views plus the All Devices table). (2) Moves `device_remote_group` (`area_auto` | `group:<id>` | `all`) into canonical per-Device `save_device_config` (`DEVICE_TEXT_KEYS` + `config.device_remote_group` in `build_studio_state_payload`, validated against configured `remote_groups`) on **Device → Interface → Remote Controls** (with a **Manage Remote Groups** footer link to `System → Media & Remotes`), retires the cross-scope `set_device_remote_group` System command (`STUDIO_REV` `3 → 4`), and turns **Device Assignments** on **System → Media & Remotes** into a read-only status list showing each screen-equipped Device's assignment chip and a **Configure** shortcut button to `/latter/devices/<id>/interface`.
- **Why:** Keeps `System → Media & Remotes` strictly focused on defining System-wide remote inventory, volume overrides, and Remote Control Groups without mutating per-Device subentry settings across scope boundaries, gives each Device an explicit home for its Remote Control Group assignment alongside its other on-screen app settings, balances card density so **Wallpapers** is no longer buried at the bottom of a 500-line column, and makes the Device sidebar scannable at a glance with concise single-word nouns.
- **Alternatives:** Keep all 6 cards on a single `Display` or `Interface` tab (leaves an oversized 6-card view and forces TV remote assignment under `Display`); keep duplicate editable remote-group dropdowns on both `System → Media & Remotes` and `Device → Interface` (maintains two mutation paths for one Device subentry key).
- **Status:** Accepted.
