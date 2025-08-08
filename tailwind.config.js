module.exports = {
  daisyui: {
    themes: [
      {
        pokemon: {  // Custom theme name
          "primary": "#0075BE",  // Blue from Pokémon logo (buttons, accents)
          "secondary": "#FFCC00",  // Yellow (highlights, warnings)
          "accent": "#A82028",  // Red (errors, calls-to-action like Save Changes)
          "neutral": "#304160",  // Dark blue-grey (borders, text)
          "base-100": "#FFFFFF",  // White background (minimal clean)
          "base-200": "#F0F0F0",  // Light grey for hovers/subtle bgs
          "info": "#3FA129",  // Green for Grass-type or success messages
          "success": "#3FA129",  // Reuse for consistency
          "warning": "#FAC000",  // Yellow for Lightning or alerts
          "error": "#D8223B",  // Red for Fire or errors
        },
      },
    ],
  },
  plugins: [require("daisyui")],
};