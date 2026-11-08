// Registers the "latter:logo" icon for Home Assistant's sidebar entry of Latter Studio.
// Loaded on every Home Assistant page (frontend extra module), so it only defines one icon.
// Contract: window.customIcons[set].getIcon(name) -> {path, viewBox} (HA frontend src/data/custom_icons.ts).
const LATTER_LOGO_PATH =
  "M4 5.5A1.5 1.5 0 0 1 5.5 4h1A1.5 1.5 0 0 1 8 5.5v13A1.5 1.5 0 0 1 6.5 20h-1A1.5 1.5 0 0 1 4 18.5v-13Z" +
  "M16 5.5A1.5 1.5 0 0 1 17.5 4h1A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-1A1.5 1.5 0 0 1 16 18.5v-13Z" +
  "M4 16.5h16v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2ZM8 5.25h8v2.5H8v-2.5ZM8 10.75h8v2.5H8v-2.5Z";

window.customIcons = window.customIcons || {};
window.customIcons.latter = {
  getIcon: async () => ({ path: LATTER_LOGO_PATH, viewBox: "0 0 24 24" }),
};
