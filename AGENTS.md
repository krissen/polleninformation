# AGENTS.md

## Automated Agent Instructions

### Directory and File Handling

- In the `custom_components/polleninformation/translations/` directory, do not change the content of the non-English files (new strings, rewording, etc.) on your own initiative — edit `en.json` and leave the rest to the maintainer. Two exceptions: mechanical changes required for validation compliance (e.g. HACS rules) may be applied across all translation files, and so may content changes the maintainer has explicitly requested or reviewed. Regardless of which case applies, all translation files must stay structurally complete: every file carries the same keys as `en.json`, with English text as a placeholder where no translation is available.

### Coding Principles

- All code must follow the KISS (Keep It Simple, Stupid) and DRY (Don't Repeat Yourself) principles.

### Comments and Documentation

- All code should be commented for clarity.
- All documentation, including comments, must be written in English.

