/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: { 950: "#06142B", 900: "#0B2545", 800: "#13315C", 700: "#1D4373", 600: "#2A5A94" },
        brand: { 50: "#EEF4FC", 100: "#D9E6F8", 500: "#2E6BD1", 600: "#2459B3", 700: "#1C4791" },
        gold: { 400: "#D8B25A", 500: "#C49A3A" },
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans Arabic", "system-ui", "sans-serif"],
        ar: ["IBM Plex Sans Arabic", "Inter", "system-ui", "sans-serif"],
      },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.06)" },
    },
  },
  plugins: [],
};
