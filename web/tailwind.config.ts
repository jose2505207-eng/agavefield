import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Earthy agave identity (light-first)
        canvas: "#FAFAF7",
        ink: { DEFAULT: "#1B2A1E", soft: "#3A4A3D", muted: "#6B7A6E" },
        agave: {
          DEFAULT: "#2E6B4F",
          deep: "#1F4D38",
          light: "#E7F0EA",
          ring: "#3E8B66",
        },
        clay: { DEFAULT: "#C06B43", light: "#F6E7DD" },
        sand: "#F2EEE4",
        line: "#E4E7E0",
        // status palette
        ok: "#2E6B4F",
        warn: "#B26A00",
        danger: "#B23B3B",
        info: "#2F6F8F",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica", "Arial", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(27,42,30,0.04), 0 4px 16px rgba(27,42,30,0.06)",
        lift: "0 6px 24px rgba(27,42,30,0.10)",
      },
    },
  },
  plugins: [],
};

export default config;
