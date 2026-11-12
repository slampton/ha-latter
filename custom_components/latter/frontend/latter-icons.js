// Registers the "latter:logo" icon for Home Assistant's sidebar entry of Latter Studio.
// Loaded on every Home Assistant page (frontend extra module), so it only defines one icon.
// Contract: window.customIcons[set].getIcon(name) -> {path, viewBox} (HA frontend src/data/custom_icons.ts).
const LATTER_LOGO_PATH =
  "M1.047 19.011L7.016 9.448A0.969 0.969 0 0 1 8.663 10.476L5.908 14.89L12.724 14.89" +
  "A2.28 2.28 0 0 1 14.659 18.377L13.621 20.039A0.969 0.969 0 0 1 11.974 19.011" +
  "L13.012 17.349A0.339 0.339 0 0 0 12.724 16.831L4.697 16.831L2.694 20.039A0.969 0.969 0 0 1 1.047 19.011Z" +
  "M22.953 4.989L16.984 14.552A0.969 0.969 0 0 1 15.337 13.524L18.092 9.11L11.276 9.11" +
  "A2.28 2.28 0 0 1 9.341 5.623L10.379 3.961A0.969 0.969 0 0 1 12.026 4.989" +
  "L10.988 6.651A0.339 0.339 0 0 0 11.276 7.169L19.303 7.169L21.306 3.961A0.969 0.969 0 0 1 22.953 4.989Z";

window.customIcons = window.customIcons || {};
window.customIcons.latter = {
  getIcon: async () => ({ path: LATTER_LOGO_PATH, viewBox: "0 0 24 24" }),
};
