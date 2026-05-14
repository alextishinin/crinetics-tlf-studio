import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        // Crinetics brand palette
        // Teal #5BAFB9 → primary action color (buttons, active nav, links)
        // Slate #5A6065 → headings + body text
        // Backgrounds remain pure white per brand guidance.
        crinetics: {
          teal: "hsl(185 36% 54%)",            // #5BAFB9
          tealDark: "hsl(185 36% 44%)",        // hover / pressed
          tealLight: "hsl(185 36% 92%)",       // subtle teal tint for active-nav backgrounds
          slate: "hsl(213 6% 38%)",            // #5A6065
        },
        border: "hsl(214 20% 90%)",
        input: "hsl(214 20% 90%)",
        ring: "hsl(185 36% 54%)",              // focus ring uses brand teal
        background: "hsl(0 0% 100%)",
        foreground: "hsl(213 6% 18%)",         // darker slate for body text
        primary: {
          DEFAULT: "hsl(185 36% 44%)",         // slightly darker for AA contrast on white
          foreground: "hsl(0 0% 100%)",
        },
        secondary: {
          DEFAULT: "hsl(213 10% 96%)",
          foreground: "hsl(213 6% 25%)",
        },
        destructive: {
          DEFAULT: "hsl(0 70% 50%)",
          foreground: "hsl(0 0% 100%)",
        },
        muted: {
          DEFAULT: "hsl(213 10% 96%)",
          foreground: "hsl(213 6% 46%)",
        },
        accent: {
          DEFAULT: "hsl(185 36% 92%)",
          foreground: "hsl(185 36% 25%)",
        },
        card: {
          DEFAULT: "hsl(0 0% 100%)",
          foreground: "hsl(213 6% 18%)",
        },
      },
      borderRadius: {
        lg: "0.5rem",
        md: "calc(0.5rem - 2px)",
        sm: "calc(0.5rem - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
