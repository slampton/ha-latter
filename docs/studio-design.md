# Latter Studio design guide

This guide is the standard for Latter Studio, the admin panel in the Home Assistant sidebar (`custom_components/latter/frontend/latter-studio.js`). Read it before changing Studio. Every change to Studio follows it. The parts that can be checked automatically are enforced by the project's verification checks, named in brackets below (for example `[STUDIO TOKENS]`).

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

- **Card**: header (title and actions on the right) → content → optional footer actions separated by a divider. A card has a description line only for a warning, a consequence or a prerequisite the controls don't show (D-012).
  ```html
  <section class="card">
    <div class="card-header">
      <div class="card-heading"><h2 class="card-title">…</h2><p class="card-description">…</p></div>
      <div class="card-header-actions">…</div>
    </div>
    <div class="card-content">…</div>
    <div class="card-actions">…</div>
  </section>
  ```
- **Collapsible card**: a native `<details class="card">` whose `<summary>` is the card header. Used for long or advanced content (logs, raw entity inspector). Inside a card, a nested collapsible section uses `details.sub-collapsible`.
- **Settings row**: label and optional description on the left, the control on the right; no divider between rows (as ha-settings-row), except between rows stacked in a narrow card. Every Latter option and every curated Device setting goes through this one row, built by `settingsRowHtml()`: `.settings-list` > `.settings-row` > `.settings-row-text` (`.row-label`, `.row-description`) + `.settings-row-control`. `.settings-row.stacked` puts a wide control (a slider, a picker) under the label.
- **Switch**: one style for every on/off setting, drawn like ha-switch (48 × 24 outlined track, 18 px thumb): `<input type="checkbox" class="switch" role="switch">`.
- **Text field and select**: Home Assistant's filled field: form background, 4 px top corners, a 1 px underline that becomes a 2 px primary line on focus. Native `<select>` keeps its own popup, drawn in Home Assistant's light or dark scheme.
- **Segmented control**: for a small either/or choice that changes the rest of a card (Notifications & Announcements: Notification or Announcement): `.segmented` with `role="radiogroup"` and `role="radio"` buttons using `aria-checked`.
- **Key/value rows**: `.kv-list` > `.kv-row` (label, value); unknown values show `—`. A row that opens something is a `button.kv-row`.
- **Lists**: `.list-row` (with `.list-row-main` and `.list-row-grow`) for short item lists with actions; `.list-block` for an item with a heading row (`.list-row-head`) and stacked fields (`.stacked-field`, `.field-label`).
- **Tables**: for lists longer than a few rows: `.table-wrap` > `table.data-table`. Sortable headers are `button.sort-btn` inside a `th` with `aria-sort`. Each row is focusable (`tabindex="0"`) and opens its item on click, Enter or Space.
- **Chips**: one shape, `.chip`, with variants `.chip-primary`, `.chip-success`, `.chip-warning`, `.chip-error` (no class is neutral). Status dots (`.status-dot`) use the same variants.
- **Empty state**: `emptyStateHtml()` renders `.empty-state`: a sentence that says what's missing and, where possible, how to add it. Never hidden.
- **Loading state**: `.loading-state`, shown until the first payload arrives; the page is never pre-filled with fake values. If the first load fails, an `.alert.alert-error` with a Retry button replaces it.
- **Error state**: every failed command shows an error toast (`.toast.error`) with the reason, from the one place that sends commands. A persistent problem (a Device health issue, a missing required entity) shows as an inline `.alert` (`.alert-warning`, `.alert-error`) in the card it affects.
- **Buttons**: pill-shaped like ha-button. `.btn` plus one variant: `.btn-primary` (accent: the main action), `.btn-secondary` (filled: a tonal primary fill), `.btn-text` (plain), `.btn-danger` (danger fill), `.btn-danger-filled` (loud danger, only inside a confirmation dialog). At most **one primary button per card** (D-009); the page header has no Save button (D-010). Two sizes: regular, and `.btn-compact` for buttons inside rows. Icon-only buttons are `.btn-icon` (`.btn-icon.danger` for delete) and always have an `aria-label`.
- **Dialogs**: a native `<dialog class="studio-dialog">`, opened with `openDialog()` and closed with `closeDialog()`. Esc closes it, focus moves into the dialog on open and returns to the opener on close. Confirmation dialogs say exactly what will happen.
- **Health**: Studio shows Latter's Home Assistant repairs and nothing else as health: a Device's repairs as one inline alert at the top of its Overview, and every Latter repair in the Issues card of the System's Overview. Both link to Home Assistant's Repairs page, where the repairs are fixed. Studio never computes a health warning of its own.
- **Accessibility**: every control has a visible label or an `aria-label`; a set of toggle pills is a `role="group"` with a label; a pointer-only picker (the color wheel) always has a keyboard equivalent next to it (a native color input and a hex field); a segmented control is one tab stop and the arrow keys move between its options; text stays in the normal text color (a danger card or dialog shows danger with its border and its filled confirm button, not with red text, which fails contrast on dark themes).
- **View layout** (D-014): a view is `[wide cards] .columns > .column + .column [wide cards]`. Each `.column` is an independent stack, so cards flow top to bottom in their own column and a short card never leaves a gap beside a tall one. Below 760 px of content width the columns become one (the first column, then the second). Only a card with wide content (a log, a table, a gallery) spans the full width, and it goes first or last in the view. A view's cards are assigned to columns in the template; there is no auto-placing grid.
- **Narrow layouts**: cards are size containers; below 520 px of card width, settings rows and list rows stack (a container query, not a viewport media query), so a card in a narrow column behaves like a card on a phone.

## 5. Navigation

- Two scopes, selected at the top of the sidebar: **Devices** first and the default landing page (the Device list), **System** second (`[STUDIO DEFAULT VIEW]`).
- The URL follows the page, so reload and Back keep it:

  | URL | Page |
  | :--- | :--- |
  | `/latter` | Device list (the default) |
  | `/latter/devices/<subentry_id>` | That Device's Overview |
  | `/latter/devices/<subentry_id>/<page>` | `overview`, `display`, `audio`, `power`, `settings` |
  | `/latter/system/<page>` | `overview`, `shared`, `remotes`, `groups`, `presence`, `settings` |

  Studio writes the URL with `history.pushState` and a `location-changed` event, the way Home Assistant's own panels navigate. An unknown path shows the Device list.
- The **Visit** link on a Latter Device's Home Assistant device page opens that Device in Studio (`/latter/devices/<subentry_id>`).
- Studio's entry in Home Assistant's sidebar shows the Latter mark, `latter:logo` (D-017). Studio's own toolbar shows only the title, as Home Assistant's toolbars do.
- The page template starts in the Devices state, so nothing flashes before the first render.
- View names are unqualified, because the scope (Devices or System) is always shown; a name is qualified only if two views in the same scope would collide (D-018). The Device list is **All Devices**; Device pages are **Overview**, **Display & Home**, **Audio & Voice**, **Power & Battery**, and **Settings**; System pages are **Overview**, **Shared Entities**, **Media & Remotes**, **Groups & Profiles**, **BLE & Area Presence**, and **Settings**. A nav label and its page title are the same text.
- A Device's **Overview** has one **Status** card (status, firmware, SDK revision, Area, battery, Wi-Fi signal, IP address, speaker, now playing, location mode, nearest BLE proxy, hardware model, group) next to **Quick Actions**. Uptime isn't shown: the firmware doesn't report it.
- One name per concept: **Device** (a Latter Device, with or without a screen; "display" only means the screen), **BLE Tag** (a tracked phone, watch or tag), **Remote Controls**, **Configuration Profile**, **Notification** (on-screen) and **Announcement** (spoken), **Settings** (never "options"), **Power & Battery**.
- A Device's **Settings** page has five cards, in this order: **Device** (node name, group), **Location & BLE** (Area tracking, fallback Area, BLE target, external Area sensor), **In Home Assistant** (device page, diagnostics file, replace hardware), **Diagnostics** (collapsed: network and status entities, a **Developer** group with the profiler, memory and weather simulation, and every entity), and **Danger Zone** (reset, remove). Settings that shape what the screen shows (such as Area cards per page) live on **Display & Home**, not here.
- System pages work fully with no Device selected. A System action that acts on one Device names that Device in the action itself (a picker), never the "selected Device" of another page.

## 6. Content rules

- Use Home Assistant and IT terminology: **System**, **Sites**, **Areas**, **Devices**, **Roles**, **Policies**, **Bridges**. Never "household", "fleet", or "room" (`[STUDIO TERMINOLOGY]`).
- No marketing device names or personal equipment brands in labels or logic; Studio branches on hardware-manifest traits.
- **Titles and labels** use Title Case: every word capitalized, including each part of a hyphenated word, except a, an, the, and, or, of, to, in, on, for, with and &, unless first or last (D-013, `[STUDIO TITLE CASE]`). That covers page and nav names; card, section, sub-section and dialog titles; settings-row, key/value, field and switch labels; table headers; tabs and segmented options; and buttons. Body text, descriptions, placeholders, select options, chips, toasts and error messages stay in sentence case. Entity names shown from a Device come from its firmware and are shown as they are. Terminology words (System, Device, Area, …) and proper names (Home Assistant, Music Assistant, ESPHome, Voice Follows Me, Repairs) always keep their capitals. Help text is one short sentence that says what the setting does, not how it's built.
- Show entity IDs only where the user picks or inspects an entity.
- Units, numbers, and dates follow the user's Home Assistant settings (`hass.locale`, `hass.config.unit_system`). Times are relative ("2 min ago") where that reads better. Studio formats them with one set of helpers: `fmtNumber`, `fmtPercent`, `fmtDistance` (feet or metres by the unit system), `fmtAgo`, and `fmtDateTime` (the user's time zone setting, server or browser). The backend sends timestamps as UTC ISO 8601 and never formats them.

## 7. Engineering rules

- Studio is a `panel_custom` web component (`require_admin=True`, `embed_iframe=False`). It talks to Home Assistant only through admin-gated `websocket_api` commands (`latter/system/*` and `latter/device/*`).
- Every command the UI calls exists in the backend, and every backend command is used by the UI (`[STUDIO COMMANDS]`).
- The websocket type is the scope: `latter/system/*` never acts on the selected Device (a System command that acts on one Device names it in its own payload), and `latter/device/*` acts on the Device named by its required `subentry_id`.
- The backend never acts on a client-chosen `entity_id` or `src` that it hasn't validated. Device entity actions are limited to the bound Device's own entities; bulk System actions are limited to the shared controls the backend itself offers; image URLs are minted and signed by the backend.
- Every Latter HTTP view requires a scoped, expiring HMAC signature (`resource_signing.py`). Studio never builds or signs a URL itself.
- No Home Assistant frontend internals: no `hass-subpage`, no walking other components' shadow roots, no `localStorage.hassTokens`, no `fetch` with stored tokens.
- Home Assistant's own pages (a device page, Repairs, the Latter integration, logs) open in the same tab with `openHaPage()` (the history API and a `location-changed` event, as Home Assistant's panels navigate), so Back returns to Studio. Studio never opens Home Assistant's dialogs or flows itself; it opens the page that has them. A download from a Home Assistant API (diagnostics) uses a short-lived path signed by Home Assistant's `auth/sign_path` command.
- Studio uses its own CSS rather than Home Assistant's internal `ha-*` elements (`ha-card`, `ha-switch`, …), which aren't a stable public API. It looks like them by using the same theme variables.
- The entity catalog (every entity offered in Studio's pickers) is the largest part of the payload, so only `get_state`, the first subscription answer and the first live push after an entity, device or Area registry change carry it; command answers and other pushes leave it out and Studio keeps the last one (`studio/catalog_gate.py`). A new payload field must earn its place: Studio renders it.
- Settings apply as they change (D-010). System settings and Device settings are written by separate commands with only the changed keys, and saving one never writes the other.

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
- **Status:** Accepted.

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
- **Status:** Accepted.

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
- **Status:** Accepted.
