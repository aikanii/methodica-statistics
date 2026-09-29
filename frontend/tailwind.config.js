/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10252E",
        pine: "#0F4C5C",
        copper: "#C45C26",
        moss: "#2D6A4F",
        paper: "#F6F1EA",
        cream: "#FBF7F1",
        mist: "#E7EEF0",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "Segoe UI", "system-ui", "sans-serif"],
        serif: ['"Fraunces"', "Georgia", "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,37,46,0.06), 0 8px 24px rgba(16,37,46,0.06)",
      },
    },
  },
  plugins: [],
};
