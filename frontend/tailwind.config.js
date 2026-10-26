/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef0ff",
          100: "#e0e3ff",
          200: "#c6caff",
          300: "#a3a7fe",
          400: "#7f7ffa",
          500: "#6461f3",
          600: "#4a4af4",
          700: "#3c37cf",
          800: "#3230a7",
          900: "#2d2e84",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
