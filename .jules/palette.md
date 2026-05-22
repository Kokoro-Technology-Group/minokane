## 2024-05-22 - Dynamic unique IDs for template ARIA bindings
**Learning:** When generating interactive elements (like radios and expandable details) dynamically from `<template>` elements in this Astro codebase, static IDs in the template will be duplicated, breaking accessibility bindings like `aria-labelledby` and `aria-controls`.
**Action:** When working with `<template>` generated DOM elements in `.astro` files, explicitly assign unique IDs (e.g. `option-text-${idx}`) via JavaScript to ensure correct screen reader relationship bindings.
