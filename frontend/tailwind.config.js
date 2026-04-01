/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:      "#0a0a10",
        card:    "#13131c",
        card2:   "#1c1c28",
        border:  "#2a2a38",
        accent:  "#d946ef",
        accent2: "#a855f7",
        pink:    "#f472b6",
        pos:     "#4ade80",
        neg:     "#fb7185",
        txt:     "#f0f0ff",
        txt2:    "#8888aa",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
