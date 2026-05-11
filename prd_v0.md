## PRD
**Product:** Ambient Superforecasting - Operationalized Questions MVP

**Goal:** An automated (and integrated) forecasting system that takes in natural-language questions from the user and operationalizes them.

## Problem Context
The most direct form of strategic awareness is simply knowing what's likely to happen. Today, when people want to understand how situations might develop, they mostly rely on intuition, pundit commentary, or — if they're unusually diligent — tracking down relevant prediction markets or expert forecasts. But this is slow and effortful, and even experts are often poorly-calibrated. Future AI driven technologies could make general forecasting as much of a science as weather forecasting is today,3 and calibrated probabilistic predictions as accessible as a search query.

## User Groups
- MVP: Me, a serious individual forecaster with a strong track record of success.

## MVP Outcome
- User enters a natural-language forecast question.
   - If the user hasn't precisely specified an operational form of the question (eg all forecasts need clear resolution criteria), the aystem creates an operationalized version of the question for the user to choose from via a selector UI.
- System creates a set of modular questions/subcomponents that address the Operationalized Question.
- _Key detail: The user could have already created an Operationalized Question that does not require modular subcomponent questions._

## Scope
### In scope
- Tech: Question operationalization and modularization.
- Tech: Short explanation of underlying questions along with confidence of importance (high, medium, low) and an LLM baseline liklihood to happen (high, medium, low)
- Docs: Update the README for how to run, test, and implement.

### Resolution Criteria
1. Unambiguous Resolution Criteria: The outcome requires objective verification. Specify a single, authoritative data source to judge the result. Eliminate all room for interpretation.
2. Precise Timeframe: Define an exact deadline down to the minute and time zone. Use strict, specific dates instead of vague windows.
3. Mutually Exclusive and Exhaustive Options: The possible answers must cover all scenarios without overlapping. Binary formats work best. If using ranges, ensure every possible number falls into exactly one bucket.
4. Clear Void Conditions: State exactly what invalidates the question. Outline the exact scenarios that cancel the forecast if the underlying premise changes.

### Core features
- **Question intake:** Natural-language prompt box with deadline and outcome fields.
- **Operationalization chooser:** Show alternate formal versions of the same question and customization of that selection (ie update the date with pre-selected options that make sense)
- **A series of agent files:** As in, a persona for various agents to provide a baseline of what an expert (or series of experts) to create the final an answer. Make sure the roles you suggest are relevant to this MVP project and have a well-defined, descriptive name. Give them distinct personalities and viewpoints. Ensure the persona prompts reflect diverse perspectives, encouraging them to offer a range of insights and predictions. Some example personas are: Modularized Question Asker; Constructive Critic with veto power; A Mathematically minded person; and A business executive who favors clear, concise, descriptive explanations.

## UX principles
- Main input should be a simple text box for the user with a clean, minimal design. Make sure to use the `kokoro-website` style `global_style.css` for fonts and colors. If you do not have access, let me know and I'll copy-paste that in my review.
- Make the operationalization visible and able to be edited (eg easily update the resolution criteria)
- Keep final output explanations concise, decision-relevant and in an executive tone of voice

## Tech stack 
- **Backend:** Python, FastAPI (make sure to use Anaconda's package manager and call it `minokane`)
- **LLM orchestration:** LangGraph, OpenRouter, and other software packages to set up the agent workflow. 
- **LLM Choice:** Let's stick with 1 for now and let's use Claude Code.
- **Frontend:** TypeScript, Astro.
- **Datebase:** For the MVP, store data into a JSON for quick review. Note, just overwrite the same file as we'll later scope/implement a better database design.

## Data model
1. User's Original Question
2. Operationalized Questions for user to choose from and the winning selection (or if further revisions were needed)
3. Modularized Operational Questions as necessary
- Domain tag and confidence tag. [forethought](https://www.forethought.org/research/design-sketches-tools-for-strategic-awareness)

## Risks
- Overconfident outputs.
- Poorly posed questions.
- False trust from polished explanations.

See more at [Forethought](https://www.forethought.org/research/design-sketches-tools-for-strategic-awareness)