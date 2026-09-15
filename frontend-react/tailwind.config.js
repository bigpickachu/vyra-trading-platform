/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0a0a0f", card: "#1a1625" },
        text: { DEFAULT: "#fafafa", muted: "#a1a1aa" },
        accent: { DEFAULT: "#a855f7", hover: "#9333ea" },
        success: "#22c55e",
        danger: "#f43f5e",
      }
    },
  },
  plugins: [],
}