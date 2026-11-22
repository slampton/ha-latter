/**
 * Latter Studio Design System Tokens (`:host`, `:host([dark])`), RTL Root Reset,
 * Upgrade/Offline Banners, Reduced-Motion Reset, & Composed `STUDIO_STYLES` (`docs/studio-design.md` §3, `D-061`, `D-066`).
 * Literal font sizes, pixel spacing, and colors appear ONLY inside `:host` / `:host([dark])`.
 */

import { css } from "../lib/lit.js";
import { CARD_STYLES } from "./cards.js";
import { CONTROL_STYLES } from "./controls.js";
import { DATA_STYLES } from "./data.js";
import { DIALOG_STYLES } from "./dialogs.js";
import { LAYOUT_STYLES } from "./layout.js";

export const TOKEN_STYLES = css`
  :host {
    /* Typography & spacing scale */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.6);
    --studio-line-height-condensed: var(--ha-line-height-condensed, 1.2);
    --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
    --studio-card-title-tracking: -0.012em;
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-card-top: var(--ha-space-5, 20px);
    --studio-space-5: var(--ha-space-6, 24px);

    /* Radii & geometry */
    --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-field: var(--ha-border-radius-sm, 4px);
    --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
    --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-card-border-width: var(--ha-card-border-width, 1px);
    --studio-control-height: var(--ha-button-height, 40px);
    --studio-control-height-compact: 32px;
    --studio-row-min-height: 56px;
    --studio-header-height: var(--header-height, 56px);
    --studio-sidebar-width: 244px;

    /* Surfaces & borders */
    --studio-bg: var(--primary-background-color, #fafafa);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #ffffff));
    --studio-surface-alt: var(--secondary-background-color, #f0f0f0);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #ffffff));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #212121));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #616161));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #ffffff));
    --studio-input-bg: var(--input-fill-color, rgba(0, 0, 0, 0.04));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #f5f5f5));
    --studio-field-bg-hover: var(--ha-color-form-background-hover, var(--studio-field-bg));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(0, 0, 0, 0.42)));
    --studio-popup-bg: var(--card-background-color, #ffffff);
    --studio-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    --studio-text: var(--primary-text-color, #212121);
    --studio-text-secondary: var(--secondary-text-color, #5f6368);
    --studio-text-disabled: var(--disabled-text-color, #9e9e9e);
    --studio-primary: var(--primary-color, #007299);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 0, 154, 199), 0.12);
    --studio-hover: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.06);

    /* WCAG 2.2 AA (>= 4.5:1) tonal fill/text pairs for buttons, active nav, & semantic chips */
    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, var(--primary-color, #007da3));
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, var(--studio-btn-accent-bg));
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, var(--text-primary-color, #ffffff));
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, #c2e6f2);
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, #005b78);
    --studio-btn-plain-hover: var(--ha-color-fill-primary-quiet-resting, var(--studio-primary-tint));
    --studio-nav-active-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-nav-active-text: var(--ha-color-on-primary-normal, #005b78);

    --studio-chip-primary-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-chip-primary-text: var(--ha-color-on-primary-normal, #005b78);
    --studio-chip-success-bg: var(--ha-color-fill-success-normal-resting, #dcf2df);
    --studio-chip-success-text: var(--ha-color-on-success-normal, #1b5e20);
    --studio-chip-warning-bg: var(--ha-color-fill-warning-normal-resting, #fff0d1);
    --studio-chip-warning-text: var(--ha-color-on-warning-normal, #7a4900);
    --studio-chip-danger-bg: var(--ha-color-fill-danger-normal-resting, #fbe4e2);
    --studio-chip-danger-text: var(--ha-color-on-danger-normal, #9e1c13);

    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, #fbe4e2);
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, #9e1c13);
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, #c62828);
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);

    /* Switch, status, shadows, & scroll masks */
    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #e0e0e0));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #616161));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, #d8eff7));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, #005b78));
    --studio-switch-thumb-shadow: var(--ha-switch-thumb-box-shadow, var(--ha-box-shadow-s, 0 1px 2px rgba(0, 0, 0, 0.3)));
    --studio-toast-bg: var(--primary-text-color, #212121);
    --studio-toast-text: var(--card-background-color, #ffffff);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(140, 140, 140));
    --studio-success: var(--success-color, #2e7d32);
    --studio-warning: var(--warning-color, #ef6c00);
    --studio-error: var(--error-color, #c62828);
    --studio-info: var(--info-color, #0277bd);
    --studio-warning-tint: color-mix(in srgb, var(--studio-warning) 14%, transparent);
    --studio-error-tint: color-mix(in srgb, var(--studio-error) 14%, transparent);
    --studio-info-tint: color-mix(in srgb, var(--studio-info) 14%, transparent);
    --studio-card-shadow: var(--ha-card-box-shadow, none);
    --studio-handoff-surface: color-mix(in srgb, var(--studio-primary) 8%, var(--studio-surface));
    --studio-handoff-ring: inset 0 0 0 1px var(--studio-primary);
    --studio-card-handoff-shadow: inset 0 0 0 1px var(--studio-primary), var(--studio-card-shadow);
    --studio-overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --studio-scrim: rgba(0, 0, 0, 0.5);
    --studio-media-bg: var(--secondary-background-color, #000000);
    --studio-photo-badge-bg: rgba(0, 0, 0, 0.68);
    --studio-photo-badge-text: #ffffff;
    --studio-photo-ring-selected: 0 0 0 2px var(--studio-primary);
    --studio-dropzone-bg: color-mix(in srgb, var(--studio-primary) 6%, var(--studio-input-bg));
    --studio-nav-scroll-mask: linear-gradient(
      to right,
      transparent 0,
      #000000 12px,
      #000000 calc(100% - 16px),
      transparent 100%
    );

    display: block;
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--studio-bg);
    color: var(--studio-text);
    font-family: var(--studio-font-family);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
    color-scheme: light;
    scrollbar-color: var(--studio-scrollbar-thumb) transparent;
    scrollbar-width: thin;
  }

  :host([dark]) {
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #282828);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #9b9b9b));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, rgba(255, 255, 255, 0.05));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #363636));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(255, 255, 255, 0.42)));
    --studio-popup-bg: var(--card-background-color, #1c1c1c);
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #a8a8a8);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #38bdf8);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);

    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, #006a8e);
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, #007da3);
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, #ffffff);
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, #104559);
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, #7bd6f5);
    --studio-nav-active-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-nav-active-text: var(--ha-color-on-primary-normal, #7bd6f5);

    --studio-chip-primary-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-chip-primary-text: var(--ha-color-on-primary-normal, #7bd6f5);
    --studio-chip-success-bg: var(--ha-color-fill-success-normal-resting, #143619);
    --studio-chip-success-text: var(--ha-color-on-success-normal, #81e287);
    --studio-chip-warning-bg: var(--ha-color-fill-warning-normal-resting, #3b2a07);
    --studio-chip-warning-text: var(--ha-color-on-warning-normal, #ffd166);
    --studio-chip-danger-bg: var(--ha-color-fill-danger-normal-resting, #3d1614);
    --studio-chip-danger-text: var(--ha-color-on-danger-normal, #ff9b93);

    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, #3d1614);
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, #ff9b93);
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, #c62828);
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);

    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #202020));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #989898));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, #0b3545));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, #7bd6f5));
    --studio-toast-bg: var(--primary-text-color, #e1e1e1);
    --studio-toast-text: var(--card-background-color, #1c1c1c);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(110, 110, 110));
    --studio-success: var(--success-color, #43a047);
    --studio-warning: var(--warning-color, #ffa600);
    --studio-error: var(--error-color, #db4437);
    --studio-info: var(--info-color, #039be5);
    color-scheme: dark;
  }

  * { box-sizing: border-box; }
  .hidden { display: none !important; }
  .studio-root {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--studio-bg);
  }
  h2, h3, h4, p { margin: 0; }
  code, .mono {
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* Upgrade & offline / sleeping Device banners */
  .studio-rev-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    background: var(--studio-chip-warning-bg);
    border-block-end: 1px solid var(--studio-warning);
    color: var(--studio-chip-warning-text);
    z-index: 40;
  }
  .offline-banner,
  .alert.offline-banner {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3) var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-inline-start: 4px solid var(--studio-warning);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface);
    color: var(--studio-text);
  }
  .offline-banner-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1 1 260px;
  }
  .offline-banner-body > span {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
`;

export { CARD_STYLES, CONTROL_STYLES, DATA_STYLES, DIALOG_STYLES, LAYOUT_STYLES };

export const STUDIO_STYLES = css`
  ${TOKEN_STYLES}
  ${LAYOUT_STYLES}
  ${CARD_STYLES}
  ${CONTROL_STYLES}
  ${DATA_STYLES}
  ${DIALOG_STYLES}
`;
