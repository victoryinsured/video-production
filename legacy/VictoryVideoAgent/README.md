# Victory Video Production Agent

Author: **Manus AI**  
Version: **Windows Local Package v1.3 — All Modules, Contrast Fix, and Editable Assets Included**  
Date: **2026-06-08**

The **Victory Video Production Agent** is a Windows-ready local production package for creating Victory Framework course assets from prepared lesson scripts. This version includes the Word scripts for **Module 2 through Module 15**, the cream-card contrast fix, and the editable-assets export, so you can select and process one module at a time without manually moving files or applying separate patches.

The agent keeps the narration script separate from the slide text. The extracted lesson script is preserved as narration text, while the slide system creates concise, professional visual anchors in the Victory Framework brand style. This protects the teaching script while producing polished training-video materials.

## What the Agent Produces

| Output | Location | Purpose |
|---|---|---|
| Narration scripts | `output/scripts` | Exact extracted lesson narration text |
| Slide images | `output/slides` | Professional 1920×1080 PNG slides |
| Narration audio | `output/audio` | ElevenLabs MP3 narration when narration is enabled |
| Final videos | `output/videos` | MP4 lesson videos assembled when audio is available |
| Trackers | `output/trackers` | Excel and CSV production tracking files |
| Moodle descriptions | `output/moodle_descriptions` | Ready-to-copy lesson descriptions and video metadata |
| Review package | `output/review_package` | The final folder to review, archive, or sync to Google Drive |
| Editable assets | `output/editable_assets` and `output/review_package/editable_assets` | Canva/PowerPoint-friendly source files for future edits |

## Quick Start

This package is set to **no-cost dry-run mode** by default because `elevenlabs.enabled` is set to `false`. The first run creates extracted scripts, slides, trackers, Moodle descriptions, manifests, and review files before spending any narration credits.

First, install **Python 3.12 for Windows** from the official Python release page and make sure Python is added to PATH during installation.[1] The setup file specifically uses Python 3.12 so Windows does not accidentally build the virtual environment with Python 3.15 beta, which caused the earlier `lxml` installation failure. If you want final MP4 video assembly after narration is enabled, also install FFmpeg and make sure both `ffmpeg` and `ffprobe` are available on PATH; the FFmpeg project lists Windows executable builds from providers such as gyan.dev and BtbN.[2]

After those prerequisites are installed, unzip this package to a normal folder. A good location is your working folder, such as `C:\Users\info\Downloads\VI Agent Video\VictoryVideoAgent_Windows\VictoryVideoAgent`, or a short folder such as `C:\VictoryVideoAgent`. Double-click `SETUP_WINDOWS.bat` once. After setup finishes, use `RUN_MODULE.bat` when you want to choose a module and run it.

| Step | Action |
|---:|---|
| 1 | Delete or archive the old extracted agent folder if you are replacing a prior package |
| 2 | Extract the new ZIP to a normal Windows folder, not inside the ZIP preview window |
| 3 | Double-click `SETUP_WINDOWS.bat` once to create the Python 3.12 virtual environment |
| 4 | Double-click `RUN_MODULE.bat` to choose Module 2 through Module 15 and run it immediately |
| 5 | Review `output\review_package` before uploading anything to Moodle |
| 6 | Later, when ready for paid narration, add your ElevenLabs key and set `elevenlabs.enabled` to `true` |
| 7 | For future edits, open `output\review_package\editable_assets` and use the lesson PPTX, PNG slides, audio, script, or edit notes |

## Choosing a Module

The easiest workflow is to double-click **`RUN_MODULE.bat`**. It displays the available modules, asks for the module number, copies the correct Word script into `input_scripts`, updates `config/config.json`, and then starts the production run automatically.

The older **`RUN_ME.bat`** launcher is still included. It does not ask you to choose a module; it simply reruns whichever module is currently active in `input_scripts`. This is useful if you want to rerun the last selected module after changing a configuration setting.

| Launcher | Best Use | What It Does |
|---|---|---|
| `SETUP_WINDOWS.bat` | First-time setup or repair | Creates the Python 3.12 virtual environment and installs dependencies |
| `RUN_MODULE.bat` | Normal daily use | Asks which module to run, activates it, then starts production |
| `RUN_ME.bat` | Rerun the current module | Runs the module that is already active in `input_scripts` |

## Included Module Scripts

The folder `module_scripts` contains the full set of course module scripts that are ready for selection. The folder `input_scripts` contains only the currently active module, because the production pipeline should process one module at a time.

| Module | Included Script | Extracted Module Title |
|---:|---|---|
| 2 | `victory-framework-module2-scripts.docx` | The Engine — Getting Answers to What You Don't Know |
| 3 | `victory-framework-module3-scripts.docx` | The Ten Questions — Step 1: The Situation |
| 4 | `victory-framework-module4-scripts.docx` | The Ten Questions — Step 2: Intake (The Story) |
| 5 | `victory-framework-module5-scripts.docx` | The Ten Questions — Step 3: Rules & Policies |
| 6 | `victory-framework-module6-scripts.docx` | The Ten Questions — Step 4: Validity |
| 7 | `victory-framework-module7-scripts.docx` | The Ten Questions — Step 5: Investigate |
| 8 | `victory-framework-module8-scripts.docx` | The Ten Questions — Step 6: Responsibility |
| 9 | `victory-framework-module9-scripts.docx` | The Ten Questions — Step 7: Value |
| 10 | `victory-framework-module10-scripts.docx` | The Ten Questions — Step 8: Decision |
| 11 | `victory-framework-module11-scripts.docx` | The Ten Questions — Step 9: Document |
| 12 | `victory-framework-module12-scripts.docx` | The Ten Questions — Step 10: Communicate |
| 13 | `victory-framework-module13-scripts.docx` | Good Faith & Compliance (Runs Through Every Step) |
| 14 | `victory-framework-module14-scripts.docx` | The Strategist Layer — From Operator to Strategist |
| 15 | `victory-framework-module15-scripts.docx` | Putting It Together — Apply the Framework to Any Industry |

You should normally use `RUN_MODULE.bat` instead of manually copying files. The final ZIP keeps the working package lean by including the selectable module scripts in `module_scripts/` rather than duplicating the original upload archive.

## Configuration

The main configuration file is `config/config.json`. It is automatically updated when you choose a module with `RUN_MODULE.bat`. Narration is disabled for the first run.

| Field | Default or Managed Value | Meaning |
|---|---|---|
| `course_name` | `Victory Framework` | Course name shown in the slides and tracker |
| `module_number` | Updated by `RUN_MODULE.bat` | Module number used in filenames and trackers |
| `module_name` | Updated by `RUN_MODULE.bat` | Module title shown in slides and Moodle descriptions |
| `input_pattern` | `*.docx` | Reads the active Word script in `input_scripts` |
| `elevenlabs.enabled` | `false` | Keeps the first run free of narration/API spending |
| `delivery.copy_to_google_drive_sync_folder` | `false` | Optional later delivery to a local Google Drive folder |

For better security, leave `elevenlabs.api_key` blank and set a Windows environment variable named `ELEVENLABS_API_KEY`. The agent will read that environment variable automatically. ElevenLabs text-to-speech is handled through the ElevenLabs API text-to-speech endpoint, and the package looks up the configured voice name through the ElevenLabs voices API when needed.[3]

## Exact Script Preservation

The agent does not use an AI writer to rewrite the narration. It extracts the script, stores the script as `.txt`, and sends that text to ElevenLabs only when narration is enabled. The generated slide text is intentionally brief and supportive; it is not the narration script. This prevents accidental edits to the teaching script while still giving the video a professional visual layer.

> **Production rule:** If the script says it, the voice reads it. If a phrase appears only on a slide, it is a visual support phrase and should not be treated as the narration source.

## Folder Map

| Folder | What It Contains |
|---|---|
| `agent` | Python automation scripts |
| `config` | Editable configuration files |
| `module_scripts` | Selectable Module 2 through Module 15 Word scripts |
| `input_scripts` | The one active module script that will be processed next |
| `output/audio` | ElevenLabs MP3 narration when enabled |
| `output/slides` | Rendered slide images |
| `output/videos` | Final MP4 videos when audio is available |
| `output/trackers` | Excel and CSV trackers |
| `output/moodle_descriptions` | Moodle descriptions and storyboards |
| `output/review_package` | Final delivery-ready package |
| `output/editable_assets` | Editable lesson assets, including PPTX decks, rendered PNG slides, scripts, audio/video copies, CSV text maps, and edit notes |
| `output/logs` | Run logs and error details |

## Editing Videos Later

The finished MP4 files are flattened videos. You can upload them into Canva to trim, split, add captions, add a logo, add music, or place new text over the video, but the original slide text inside the MP4 is not a live Canva text layer.

For deeper edits, use the new editable-assets export. After each run, open `output\review_package\editable_assets`. Each lesson folder includes an `editable_slides.pptx` deck that can be uploaded to Canva or opened in PowerPoint, exact rendered slide PNGs, the narration script, narration audio when available, the finished video when available, a `slide_text.csv` map, and lesson-specific edit notes.

| Editing Need | Best File To Use |
|---|---|
| Quick trim, caption, logo, or overlay | Finished MP4 in `output\videos` |
| Change slide wording or layout later | `editable_slides.pptx` inside the lesson editable-assets folder |
| Keep the exact video look but add overlays | PNG files in `rendered_slides` |
| Reuse the same narration after visual edits | MP3 files in the lesson `audio` folder |

## Restarting and Cost Control

The default configuration skips existing audio files so that a rerun does not automatically spend additional ElevenLabs usage. In this package, ElevenLabs is disabled by default, so the first run focuses on verifying script extraction, slides, trackers, and Moodle descriptions. When you are ready for narrated videos, enable ElevenLabs in `config/config.json`, add your API key, and rerun the agent.

If you switch modules with `RUN_MODULE.bat`, the selector updates only the active script and module title fields. It does not turn ElevenLabs on by itself, so you stay in dry-run mode until you intentionally enable narration.

## References

[1]: https://www.python.org/downloads/release/python-31210/ "Python 3.12.10 Release"
[2]: https://ffmpeg.org/download.html "Download FFmpeg"
[3]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert "ElevenLabs API Reference: Text to Speech"
