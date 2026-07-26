/** @type {import('tailwindcss').Config} */
// Mirrors the inline `tailwind.config` the pages used with the CDN build (darkMode: class, Inter as
// the sans font). `content` covers every HTML page and every JS file so classes composed in
// JS template literals (viewer.js / app.js / leaderboard's Alpine :class bindings) survive purging.
module.exports = {
  darkMode: "class",
  content: [
    "./*.html",
    "./js/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  // Classes selected via variable indirection (e.g. STAGE_COLOR / heatScale-driven state, and the
  // ternary state classes toggled at runtime) all appear as complete literal strings in the scanned
  // files, so the content scan already covers them. This safelist is a belt-and-braces guard for the
  // state/badge classes that only ever appear inside JS objects or Alpine expressions, plus their
  // dark: variants, in case a future edit breaks a class into concatenated fragments.
  safelist: [
    // stage badge palettes (STAGE_COLOR in viewer.js) — indigo / violet / fuchsia families
    { pattern: /^(bg|text|ring)-(indigo|violet|fuchsia|emerald|amber|red|gray)-(50|100|200|300|400|500|600|700|800|900)$/,
      variants: ["dark", "hover", "dark:hover"] },
    // opacity-suffixed dark badge backgrounds/rings (e.g. bg-indigo-500/10, ring-indigo-500/20)
    { pattern: /^(bg|text|ring)-(indigo|violet|fuchsia|emerald|amber|red)-500\/(10|15|20)$/,
      variants: ["dark"] },
    // active/inactive tab + pill states composed at runtime
    "bg-white", "shadow-sm", "hidden", "flex",
  ],
};
