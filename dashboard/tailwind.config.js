/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        defense: {
          950: "#060a0f",
          900: "#0b131d",
          850: "#0f1b29",
          800: "#152438",
          700: "#1e324d",
          600: "#2d486d",
          accent: "#00f0ff",
          danger: "#ff334b",
          warning: "#ffaa00",
          success: "#00e676",
        }
      },
      fontFamily: {
        mono: ["Consolas", "Monaco", "Courier New", "monospace"],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flash-danger': 'flashDanger 1s infinite alternate',
      },
      keyframes: {
        flashDanger: {
          '0%': { borderColor: 'rgba(255, 51, 75, 0.4)', backgroundColor: 'rgba(255, 51, 75, 0.05)' },
          '100%': { borderColor: 'rgba(255, 51, 75, 1)', backgroundColor: 'rgba(255, 51, 75, 0.2)' },
        }
      }
    },
  },
  plugins: [],
}