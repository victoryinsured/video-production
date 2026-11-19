# Victory Video Production Agent — All-Modules Windows Package Validation Notes

Validated on: **2026-06-08**

## Rebuild Summary

This package was rebuilt as a Windows-ready **all-modules** Victory Video Production Agent. It includes selectable Word scripts for **Module 2 through Module 15** in `module_scripts/`, while `input_scripts/` holds only the currently active module. This prevents accidental batch production of every module while still allowing the user to process modules one at a time through `RUN_MODULE.bat`.

| Item | Result |
|---|---|
| Selectable module folder | `module_scripts/` |
| Active input folder | `input_scripts/` |
| Included module range | Module 2 through Module 15 |
| Default active module for shipment | Module 2 — The Engine — Getting Answers to What You Don't Know |
| Main launcher for user workflow | `RUN_MODULE.bat` |
| Existing current-module launcher | `RUN_ME.bat` |
| ElevenLabs default | Disabled for first run, so setup can be tested without an API key |
| Python target on Windows | Python 3.12 |

## Selector Validation

The new `agent/select_module.py` script was tested against the packaged `module_scripts/` folder. It successfully listed all 14 bundled modules, extracted module titles from the Word metadata blocks, copied the selected module into `input_scripts/`, updated `config/config.json`, and wrote `CURRENT_MODULE.txt`.

| Check | Result |
|---|---|
| Listed Module 2 through Module 15 | Passed |
| Read titles from Word metadata | Passed |
| Activated Module 2 | Passed |
| Activated Module 3 | Passed |
| Updated `config/config.json` | Passed |
| Created `CURRENT_MODULE.txt` | Passed |

## Module 3 Dry-Run Validation

A representative validation run was performed on **Module 3 — The Ten Questions — Step 1: The Situation** with ElevenLabs disabled. The pipeline completed successfully and produced scripts, slides, trackers, Moodle descriptions, manifests, and a review package without generating paid narration audio.

| Check | Result |
|---|---|
| Active validation script | `input_scripts/victory-framework-module3-scripts.docx` |
| Word document extraction | Passed |
| Metadata-block lesson splitting | Passed |
| Lesson count | 4 lessons |
| Slide rendering | Passed — 28 slide images generated |
| Production tracker generation | Passed — Excel and CSV trackers generated |
| Moodle description generation | Passed |
| ElevenLabs narration | Skipped intentionally because narration is disabled by default |
| Video assembly | Skipped because narration audio was not generated |
| Overall pipeline result | Completed successfully |

## Extracted Module 3 Lessons

| Lesson | Title |
|---|---|
| 3.1 | What the Situation Really Is: Start Human, Not Technical |
| 3.2 | Hearing What They Actually Want |
| 3.3 | Naming the Case Without the Buzzwords |
| 3.4 | Situation Practice: Five Cases Across Five Industries |

## Packaging Notes

Before final ZIP packaging, the active module was reset to **Module 2** and generated output artifacts were removed so the ZIP opens cleanly for the user. The user should run `SETUP_WINDOWS.bat` once after extracting the package, then use `RUN_MODULE.bat` to choose and process any module from Module 2 through Module 15.

> **Important Windows note:** Install and use **Python 3.12**, not Python 3.15 beta. The setup launcher specifically calls `py -3.12` and rebuilds an incompatible `.venv` automatically if one already exists.
