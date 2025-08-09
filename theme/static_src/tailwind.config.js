// tailwind.config.js
module.exports = {
  content: [
    '../templates/**/*.html',      // Templates in the 'theme' app
    '../../templates/**/*.html',   // Root-level templates
    '../../**/templates/**/*.html'       // If you have JS components using Tailwind classes
    // Add more if needed, e.g., for Vue/React files if you expand the project
  ],
  theme: {
    extend: {},  // Optional: Add non-DaisyUI customs here, like fontFamily or spacing
  },
  plugins: [require("daisyui")],  // Loads DaisyUI—ensure it's installed (see Step 2)
};