// Registers the "latter:logo" icon for Home Assistant's sidebar entry of Latter Studio.
// Loaded on every Home Assistant page (frontend extra module), so it only defines one icon.
// Contract: window.customIcons[set].getIcon(name) -> {path, viewBox} (HA frontend src/data/custom_icons.ts).
const LATTER_LOGO_PATH =
  "M1.443 18.75L7.193 9.538A0.94 0.94 0 0 1 8.792 10.536L6.145 14.776L12.698 14.776" +
  "A2.204 2.204 0 0 1 14.567 18.147L13.568 19.748A0.94 0.94 0 0 1 11.969 18.75" +
  "L12.968 17.149A0.319 0.319 0 0 0 12.698 16.661L4.969 16.661L3.042 19.748A0.94 0.94 0 0 1 1.443 18.75Z" +
  "M22.557 5.25L16.807 14.462A0.94 0.94 0 0 1 15.208 13.464L17.855 9.224L11.302 9.224" +
  "A2.204 2.204 0 0 1 9.433 5.853L10.432 4.252A0.94 0.94 0 0 1 12.031 5.25" +
  "L11.032 6.851A0.319 0.319 0 0 0 11.302 7.339L19.031 7.339L20.958 4.252A0.94 0.94 0 0 1 22.557 5.25Z";

window.customIcons = window.customIcons || {};
window.customIcons.latter = {
  getIcon: async () => ({ path: LATTER_LOGO_PATH, viewBox: "0 0 24 24" }),
};
