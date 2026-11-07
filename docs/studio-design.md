# Latter Studio design guide

This guide is the standard for Latter Studio, the admin panel in the Home Assistant sidebar (`custom_components/latter/frontend/latter-studio.js`). Read it before changing Studio. Every change to Studio follows it. The parts that can be checked automatically are enforced by the project's verification checks, named in brackets below (for example `[STUDIO TOKENS]`).

The [decision log](#decision-log) at the end records the standing choices behind this guide.

---

## 1. Purpose and scope

Studio owns three things:

1. **Latter-only settings**: options that exist only in Latter, such as shared entities, remote groups, BLE calibration, wallpapers, the Home dock, and each Device's Latter options.
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

Studio matches Home Assistant's own settings pages. Every visual value comes from a token. Tokens are defined **once**, in the `:host` block at the top of `STUDIO_STYLES`, and each one reads a Home Assistant theme variable with a fallback. No other rule in the file contains a font size, a pixel spacing value, or a color literal.

> **Ratchet.** Studio is being migrated to these tokens. Until the migration is complete, the `[STUDIO TOKENS]` check counts the hard-coded `font-size`, pixel spacing, and color literals outside the `:host` block, and fails if the count grows. Lower the recorded count whenever a change removes some. The goal is zero.

### Type scale

| Role | Size / weight | Token | HA variable |
| :--- | :--- | :--- | :--- |
| Page title | 20 / 500 | `--studio-font-title` | `--ha-font-size-xl` |
| Section and card title | 16 / 500 | `--studio-font-section` | `--ha-font-size-l` |
| Body and row label | 14 / 400 | `--studio-font-body` | `--ha-font-size-m` |
| Secondary text | 12 / 400, `--secondary-text-color` | `--studio-font-secondary` | `--ha-font-size-s` |
| Caption (chips, table heads) | 12 / 500 | `--studio-font-caption` | `--ha-font-size-s` |

Two weights only: `--ha-font-weight-normal` (400) and `--ha-font-weight-medium` (500). Fonts come from `--ha-font-family-body` and, for code, `--ha-font-family-code`. No hard-coded font stacks: the fallback is `inherit`, so a theme's font always wins.

### Spacing

A 4 px grid: **4, 8, 12, 16, 24** (`--studio-space-1` … `--studio-space-5`, from `--ha-space-1`, `-2`, `-3`, `-4`, `-6`).

| Use | Value |
| :--- | :--- |
| Page padding | 24 (16 on narrow screens) |
| Card padding | 16 |
| Gap between cards | 16 |
| Settings row padding | 12 vertical |
| Gap between controls | 8 |

### Radii

Three radii: **card** (`--ha-card-border-radius`, 12), **control** (`--ha-border-radius-md`, 8), and **pill** (`--ha-border-radius-pill`).

### Colors

Colors come only from Home Assistant theme variables:

- Surfaces: `--primary-background-color`, `--card-background-color`, `--secondary-background-color`, `--divider-color`.
- Text: `--primary-text-color`, `--secondary-text-color`, `--text-primary-color` (text on a primary-colored surface).
- Accent: `--primary-color`; tints are `rgba(var(--rgb-primary-color), <alpha>)`, never a fixed blue.
- Status: `--success-color`, `--warning-color`, `--error-color`, `--info-color`.

Literal colors appear only as token fallbacks inside `:host`. User data (a saved color swatch, a wallpaper thumbnail) is the only exception, and it's set from data, never written in CSS.

### Token block

```css
:host {
  --studio-font-family: var(--ha-font-family-body, inherit);
  --studio-font-code: var(--ha-font-family-code, monospace);
  --studio-font-title: var(--ha-font-size-xl, 20px);
  --studio-font-section: var(--ha-font-size-l, 16px);
  --studio-font-body: var(--ha-font-size-m, 14px);
  --studio-font-secondary: var(--ha-font-size-s, 12px);
  --studio-font-caption: var(--ha-font-size-s, 12px);
  --studio-weight-regular: var(--ha-font-weight-normal, 400);
  --studio-weight-medium: var(--ha-font-weight-medium, 500);
  --studio-space-1: var(--ha-space-1, 4px);
  --studio-space-2: var(--ha-space-2, 8px);
  --studio-space-3: var(--ha-space-3, 12px);
  --studio-space-4: var(--ha-space-4, 16px);
  --studio-space-5: var(--ha-space-6, 24px);
  --studio-radius-card: var(--ha-card-border-radius, 12px);
  --studio-radius-control: var(--ha-border-radius-md, 8px);
  --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
  /* colors: surfaces, text, accent and status as listed above, each with a fallback */
}
```

## 4. Components

Studio has one implementation of each component. A new pattern is added here first, then built once and reused.

- **Card**: header (title, optional one-line description, actions on the right) → content → optional footer actions separated by a divider. Descriptions are always visible.
- **Collapsible card**: a native `<details>` with the same header. Used for long or advanced content (logs, raw entity inspector).
- **Settings row**: label and optional description on the left, the control on the right, a divider between rows. Stacks on narrow screens. Every Latter option and every curated Device setting goes through this one row. One switch style for every on/off setting.
- **Key/value rows**: a label and a value; unknown values show `—`.
- **Tables**: for lists longer than a few rows. Sortable column headers that work with the keyboard; the whole row opens its item.
- **Chips**: one chip shape with status variants (neutral, primary, success, warning, error) taken from the theme colors.
- **Empty state**: one block with a sentence that says what's missing and, where possible, how to add it. Never hidden.
- **Loading state**: shown until the first data arrives; never pre-filled with fake values.
- **Error state**: every failed command shows an error toast with the reason. A persistent problem (a Device health issue, a missing required entity) shows as an inline alert in the card it affects.
- **Buttons**: primary (filled), secondary (outlined), tertiary (text or icon), danger (outlined; filled only inside a confirmation dialog). At most **one primary button per card or view**. Two sizes: regular and compact.
- **Dialogs**: native `<dialog>`, closed with Esc, focus moved into the dialog on open and returned on close. Confirmation dialogs say exactly what will happen.

## 5. Navigation

- Two scopes, selected at the top of the sidebar: **Devices** first and the default landing page (the Device list), **System** second (`[STUDIO DEFAULT VIEW]`).
- Opening Studio, or reloading it, shows the Device list unless the URL names a Device (`/latter/devices/<subentry_id>`).
- The page template starts in the Devices state, so nothing flashes before the first render.
- Page names are unique: Device pages are **Overview**, **Display & Home**, **Audio & Voice**, **Power & Battery**, and **Device settings**; System pages are **System overview**, **Shared Entities**, **Media & Remotes**, **Groups & Profiles**, **BLE & Area Presence**, and **System settings**. A nav label and its page title are the same text.
- System pages work fully with no Device selected. A System action that acts on one Device names that Device in the action itself (a picker), never the "selected Device" of another page.

## 6. Content rules

- Use Home Assistant and IT terminology: **System**, **Sites**, **Areas**, **Devices**, **Roles**, **Policies**, **Bridges**. Never "household", "fleet", or "room" (`[STUDIO TERMINOLOGY]`).
- No marketing device names or personal equipment brands in labels or logic; Studio branches on hardware-manifest traits.
- Labels use sentence case, like Home Assistant. Help text is one short sentence that says what the setting does, not how it's built.
- Show entity IDs only where the user picks or inspects an entity.
- Units, numbers, and dates follow the user's Home Assistant settings (`hass.locale`, `hass.config.unit_system`). Times are relative ("2 min ago") where that reads better.

## 7. Engineering rules

- Studio is a `panel_custom` web component (`require_admin=True`, `embed_iframe=False`). It talks to Home Assistant only through admin-gated `websocket_api` commands (`latter/system/*` and `latter/device/*`).
- Every command the UI calls exists in the backend, and every backend command is used by the UI (`[STUDIO COMMANDS]`).
- The websocket type is the scope: `latter/system/*` never needs a selected Device unless the command names one in its own payload, and `latter/device/*` always acts on the selected Device.
- The backend never acts on a client-chosen `entity_id` or `src` that it hasn't validated. Device entity actions are limited to the bound Device's own entities; bulk System actions are limited to the shared controls the backend itself offers; image URLs are minted and signed by the backend.
- Every Latter HTTP view requires a scoped, expiring HMAC signature (`resource_signing.py`). Studio never builds or signs a URL itself.
- No Home Assistant frontend internals: no `hass-subpage`, no walking other components' shadow roots, no `localStorage.hassTokens`, no `fetch` with stored tokens.
- Studio uses its own CSS rather than Home Assistant's internal `ha-*` elements (`ha-card`, `ha-switch`, …), which aren't a stable public API. It looks like them by using the same theme variables.
- One Save per scope: System settings and Device settings are saved by separate commands, and saving one never writes the other.

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
- **Status:** Accepted.

### D-008: One media-handoff setting
- **Date:** 2026-11-07
- **Decision:** A Device has one setting for handing media to the Area it moves into, used for both BLE moves and on-device Area picks.
- **Why:** Two overlapping settings, one of them hidden, made the behavior impossible to predict.
- **Alternatives:** Show both settings with honest labels.
- **Status:** Accepted; pending the firmware change.
