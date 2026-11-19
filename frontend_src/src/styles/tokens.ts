/**
 * Composed Latter Studio Design System Stylesheet (`STUDIO_STYLES`), re-exporting
 * modular stylesheet slices (`base`, `layout`, `cards`, `controls`, `data`, `dialogs`, `narrow`).
 */

import { css } from "../lib/lit.js";
import { BASE_STYLES } from "./base.js";
import { CARD_STYLES } from "./cards.js";
import { CONTROL_STYLES } from "./controls.js";
import { DATA_STYLES } from "./data.js";
import { DIALOG_STYLES } from "./dialogs.js";
import { LAYOUT_STYLES } from "./layout.js";
import { NARROW_STYLES } from "./narrow.js";

export {
  BASE_STYLES,
  CARD_STYLES,
  CONTROL_STYLES,
  DATA_STYLES,
  DIALOG_STYLES,
  LAYOUT_STYLES,
  NARROW_STYLES,
};

export const STUDIO_STYLES = css`
  ${BASE_STYLES}
  ${LAYOUT_STYLES}
  ${CARD_STYLES}
  ${CONTROL_STYLES}
  ${DATA_STYLES}
  ${DIALOG_STYLES}
  ${NARROW_STYLES}
`;
