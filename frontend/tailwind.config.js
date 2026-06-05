// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "hsl(210, 100%, 55%)",
        "primary-foreground": "hsl(210, 20%, 98%)",
        accent: "hsl(340, 80%, 60%)",
        "accent-foreground": "hsl(340, 100%, 98%)",
        secondary: "hsl(215, 16%, 47%)",
        "secondary-foreground": "hsl(215, 20%, 95%)",
        destructive: "hsl(0, 72%, 50%)",
        "destructive-foreground": "hsl(0, 0%, 100%)",
        muted: "hsl(210, 20%, 90%)",
        "muted-foreground": "hsl(210, 10%, 40%)",
        popover: "hsl(210, 20%, 95%)",
        "popover-foreground": "hsl(210, 10%, 20%)",
        border: "hsl(216, 16%, 22%)",
        input: "hsl(216, 16%, 22%)",
        background: "hsl(210, 20%, 98%)",
        foreground: "hsl(210, 10%, 20%)",
        card: "hsl(210, 20%, 95%)",
        "card-foreground": "hsl(210, 10%, 20%)"
      }
    }
  },
  darkMode: "class",
  plugins: []
};
