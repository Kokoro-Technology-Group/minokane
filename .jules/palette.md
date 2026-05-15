## 2026-05-15 - Dynamic ARIA attributes in templates
**Learning:** When using `<template>` elements to dynamically generate repetitive UI components (like list items with inputs and text), inputs can easily lose accessible names if they rely on text within the cloned fragment. `aria-labelledby` needs to be paired with dynamically generated unique IDs (e.g. ``id=`text-${idx}```) during JS rendering.
**Action:** Always assign and track unique `id` attributes when cloning templates that contain interactive elements, and pair them immediately with `aria-labelledby` and `aria-controls`.
