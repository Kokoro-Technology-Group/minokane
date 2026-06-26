## 2025-02-13 - [Accessibility] Dynamic IDs for Template Elements
**Learning:** When using `<template>` elements to generate repetitive UI components in this app, static IDs within the template cause duplicate ID issues in the DOM. This breaks accessibility bindings like `aria-labelledby` and `aria-controls`.
**Action:** Always dynamically assign unique IDs to elements generated from templates during JavaScript rendering to maintain proper ARIA associations and screen reader support.
