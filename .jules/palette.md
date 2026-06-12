## 2024-06-12 - Accessibility Bindings in Astro Templates
**Learning:** When generating interactive components like radio buttons or disclosure widgets dynamically from an HTML `<template>` element in Astro (e.g., using `content.cloneNode(true)`), structural accessibility links like `aria-labelledby` and `aria-controls` are lost if static IDs are used.
**Action:** Always generate explicit, unique IDs during the JavaScript rendering phase and assign them to the relevant elements to maintain standard ARIA bindings.
