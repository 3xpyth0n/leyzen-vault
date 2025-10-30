const plugin = require("tailwindcss/plugin");

module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      screens: {
        xs: "360px",
        "3xl": "1920px",
        touch: { raw: "(pointer: coarse)" },
        hd: { raw: "(min-resolution: 2dppx)" },
      },
      borderRadius: {
        touch: "1.125rem",
      },
      spacing: {
        "safe-x": "max(1rem, env(safe-area-inset-left))",
        "safe-y": "max(1rem, env(safe-area-inset-top))",
      },
    },
  },
  plugins: [
    plugin(function ({ addUtilities, addComponents, theme }) {
      addUtilities(
        {
          ".touch-target": {
            minHeight: "3.25rem",
            paddingInline: theme("spacing.4"),
            paddingBlock: theme("spacing.3"),
            borderRadius: theme("borderRadius.touch"),
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: theme("spacing.2"),
          },
          ".touch-target-tight": {
            minHeight: "2.75rem",
            paddingInline: theme("spacing.3"),
            paddingBlock: theme("spacing.2"),
            borderRadius: theme("borderRadius.lg"),
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            gap: theme("spacing.1"),
          },
          ".gpu-translate": {
            transform: "translateZ(0)",
            willChange: "transform",
          },
        },
        ["responsive"],
      );

      addComponents({
        ".stack-panels": {
          display: "grid",
          gap: theme("spacing.6"),
          gridTemplateColumns: "repeat(auto-fit, minmax(18rem, 1fr))",
        },
        "@screen md": {
          ".stack-panels": {
            gap: theme("spacing.7"),
          },
        },
        "@screen lg": {
          ".stack-panels": {
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          },
        },
        "@screen 3xl": {
          ".stack-panels": {
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          },
        },
        ".glass-preserve": {
          backgroundColor: "rgba(15, 23, 42, 0.6)",
          backgroundImage:
            "linear-gradient(135deg, rgba(148, 163, 184, 0.14), rgba(30, 41, 59, 0.35))",
          border: "1px solid rgba(148, 163, 184, 0.18)",
          boxShadow: "0 24px 48px rgba(2, 6, 23, 0.45)",
          backdropFilter: "blur(14px) saturate(1.2)",
          WebkitBackdropFilter: "blur(14px) saturate(1.2)",
        },
        "@screen hd": {
          ".glass-preserve": {
            boxShadow: "0 16px 36px rgba(8, 15, 35, 0.4)",
            backgroundImage:
              "linear-gradient(135deg, rgba(148, 163, 184, 0.18), rgba(15, 23, 42, 0.45))",
          },
        },
      });
    }),
  ],
};
