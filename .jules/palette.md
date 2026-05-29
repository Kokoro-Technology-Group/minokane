## 2026-05-29 - Dynamic Accessibility Bindings
**Learning:** When using `<template>` elements to dynamically generate repetitive UI components in this Astro project, you must explicitly assign unique IDs during JavaScript rendering to correctly maintain accessibility bindings like `aria-labelledby` and `aria-controls`.
**Action:** Always generate unique IDs (e.g., using loop index) and assign them to the corresponding interactive elements and their descriptive/controlled targets when cloning template nodes.
