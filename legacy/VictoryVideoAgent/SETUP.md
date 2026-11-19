# Setup Guide — Victory Video Production Agent

Author: **Manus AI**  
Version: **Windows Local Package v1.3 — All Modules, Contrast Fix, and Editable Assets Included**  
Date: **2026-06-08**

This setup guide explains how to install and operate the **Victory Video Production Agent** on a Windows computer. This rebuilt package includes **Module 2 through Module 15**, the cream-card contrast fix, and the editable-assets export. It also includes a double-click launcher named `RUN_MODULE.bat` so you can choose a module without manually moving Word files.

The intended workflow is local-first and low-cost. Python renders the slides and controls the pipeline, ElevenLabs can produce narration audio after you enable it, FFmpeg assembles final MP4 videos when audio is available, the editable-assets exporter creates Canva/PowerPoint-friendly source files, and Google Drive for Desktop can optionally sync the finished review package to Drive.

## 1. Install the Required Software

Install **Python 3.12 64-bit** first. This is important because the setup must not use Python 3.15 beta; Python 3.15 caused the earlier `lxml` installation error on Windows. Use the official Python 3.12 release installer and select **Add python.exe to PATH** during installation.[1]

After installation, open Command Prompt and run:

```bat
py -0p
```

You should see a Python 3.12 entry. The setup file specifically calls `py -3.12`, so Python 3.12 can coexist with Python 3.14 or Python 3.15 on the same computer.

FFmpeg is required only when you want final MP4 video assembly with audio. The FFmpeg download page lists Windows executable builds, including gyan.dev and BtbN builds.[2] After installing FFmpeg, open Command Prompt and run `ffmpeg -version` and `ffprobe -version`. Both commands must work.

| Software | Why It Is Needed | How to Check |
|---|---|---|
| Python 3.12 | Runs the local production agent and installs dependencies reliably | `py -3.12 --version` |
| FFmpeg | Builds MP4 videos and joins multi-part audio | `ffmpeg -version` |
| FFprobe | Reads audio duration for slide timing | `ffprobe -version` |
| Google Drive for Desktop | Optional automatic delivery sync | Confirm files appear in Windows File Explorer |

Google Drive for Desktop is optional. Google’s help page explains that Drive for Desktop lets files appear in Windows File Explorer and sync to Google Drive automatically.[3]

## 2. Extract the Package Correctly

Unzip the package to a normal Windows folder, not inside the ZIP preview window. Your working folder can be:

```text
C:\Users\info\Downloads\VI Agent Video\VictoryVideoAgent_Windows\VictoryVideoAgent
```

A shorter location such as `C:\VictoryVideoAgent` is also fine. Avoid running the package while the Windows File Explorer address bar still shows `.zip`, because batch files and Python scripts need real extracted folders.

If you are replacing an older copy, delete or rename the old extracted `VictoryVideoAgent` folder first. Then extract this new all-modules ZIP fresh.

## 3. Run the Package Setup

Double-click `SETUP_WINDOWS.bat`. This script checks for Python 3.12, creates a private `.venv` folder, replaces an incompatible old `.venv` if it was created with Python 3.15, and installs the package dependencies listed in `requirements.txt`.

If Windows blocks the batch file, right-click the file, choose **Properties**, and select **Unblock** if that option appears. Then run it again.

| Setup File | When To Use It | Expected Result |
|---|---|---|
| `SETUP_WINDOWS.bat` | First use, after extracting the ZIP, or after a broken environment | A `.venv` folder is created with Python 3.12 dependencies installed |
| `RUN_MODULE.bat` | Normal use after setup | You choose Module 2 through Module 15 and production starts |
| `RUN_ME.bat` | Rerun the currently active module | The agent reruns the module already copied into `input_scripts` |

## 4. Understand the Included Scripts

The package includes all selectable module scripts in this folder:

```text
module_scripts
```

The agent processes only the active script in this folder:

```text
input_scripts
```

This design prevents the agent from accidentally producing every module at once. `RUN_MODULE.bat` copies the selected module from `module_scripts` into `input_scripts` and updates `config/config.json` for you.

| Folder | Contents | User Action Needed |
|---|---|---|
| `module_scripts` | Module 2 through Module 15 Word scripts | Do not move files during normal use |
| `input_scripts` | The single currently active Word script | Managed automatically by `RUN_MODULE.bat` |

## 5. First Run: Choose a Module and Stay in No-Cost Dry Run

The default configuration has ElevenLabs disabled:

```json
"elevenlabs": {
  "enabled": false
}
```

This first run creates extracted scripts, slide images, editable assets, trackers, Moodle descriptions, manifests, and a review package without spending narration credits. Double-click:

```text
RUN_MODULE.bat
```

When the window asks for a module number, enter a number from `2` through `15` and press Enter. The agent then updates the active module and starts production automatically. When the process finishes, open:

```text
output\review_package
```

Review the scripts, slide images, tracker, Moodle descriptions, and `output\review_package\editable_assets` folder before enabling paid narration.

## 6. Enable ElevenLabs Narration Later

The agent uses ElevenLabs text-to-speech to create narration audio. ElevenLabs documents text-to-speech conversion in its API reference, and this package calls that API directly from the local machine.[4]

The preferred setup is to store the API key in a Windows environment variable rather than directly in `config.json`. Open Command Prompt and run the following command, replacing `YOUR_KEY_HERE` with your actual ElevenLabs API key:

```bat
setx ELEVENLABS_API_KEY "YOUR_KEY_HERE"
```

Close Command Prompt after setting the variable. New Command Prompt windows and future double-click runs will be able to read it. In `config/config.json`, leave `elevenlabs.api_key` blank and keep `elevenlabs.api_key_env_var` set to `ELEVENLABS_API_KEY`.

| Config Field | Recommended Value When Narration Is Ready |
|---|---|
| `elevenlabs.enabled` | `true` |
| `elevenlabs.api_key` | Leave blank when using the environment variable |
| `elevenlabs.api_key_env_var` | `ELEVENLABS_API_KEY` |
| `elevenlabs.voice_id` | `Victoria Voice` or the exact ElevenLabs voice ID |
| `overwrite_existing_audio` | `false` for cost control |

If the visible voice name does not resolve, open ElevenLabs, copy the actual voice ID for Victoria’s cloned voice, and paste that into `elevenlabs.voice_id`.

## 7. Running Another Module Later

Use `RUN_MODULE.bat` again whenever you want to switch modules. The selector displays the available module numbers, asks what to run, copies the right `.docx` file into `input_scripts`, updates `module_number` and `module_name` in `config/config.json`, and starts the agent.

The package can also read either `.docx` files or `.txt` files, but you do not need that manual workflow for the included Victory Framework modules. Keep `input_pattern` as `*.docx` for the packaged scripts.

| Future-Module Step | What To Do |
|---|---|
| Choose a module | Double-click `RUN_MODULE.bat` and type the module number |
| Rerun setup? | Usually no; run setup only after moving computers or if dependencies break |
| Rerun the current module only | Double-click `RUN_ME.bat` |
| Check active module | Open `CURRENT_MODULE.txt` after using `RUN_MODULE.bat` |

## 8. Editing the Videos Later

The agent now creates editable source assets automatically after each run. Open this folder after production completes:

```text
output\review_package\editable_assets
```

Each lesson folder contains an `editable_slides.pptx` deck, exact rendered slide PNGs, the narration script, audio when available, video when available, `slide_text.csv`, and `edit_notes.md`. Upload the PPTX to Canva or open it in PowerPoint when you need deeper edits. Upload the MP4 to Canva when you only need trims, captions, logos, music, or overlays.

| Editing Task | Best File |
|---|---|
| Trim, split, caption, add logo, or add music | Finished MP4 in the lesson `video` folder |
| Change wording or adjust the slide layout | `editable_slides.pptx` |
| Overlay on the exact final slide visuals | PNG files in `rendered_slides` |
| Reuse narration without buying new audio | MP3 files in the lesson `audio` folder |

## 9. Optional Google Drive Sync Delivery

If Google Drive for Desktop is installed and signed in, create a folder in Drive such as `G:\My Drive\Victory Framework Videos`. Then edit `config/config.json`:

```json
"delivery": {
  "copy_to_google_drive_sync_folder": true,
  "google_drive_sync_folder": "G:\\My Drive\\Victory Framework Videos"
}
```

After a successful run, the agent copies the complete review package into that local Drive folder. Google Drive for Desktop handles the upload in the background, which avoids a complicated Google API authorization process.[3]

## 10. Troubleshooting

Most issues are caused by missing prerequisites, missing API keys, incorrectly formatted script headings, or running from inside the ZIP instead of the extracted folder. The agent writes detailed logs to `output/logs`.

| Problem | Likely Cause | Fix |
|---|---|---|
| `Python 3.12 was not found` | Python 3.12 is not installed or launcher cannot see it | Install Python 3.12 64-bit and check **Add python.exe to PATH** |
| `Failed building wheel for lxml` | Setup used Python 3.15 beta or another unsupported version | Delete `.venv`, install Python 3.12, then rerun `SETUP_WINDOWS.bat` |
| Path contains `.zip` | You are inside the ZIP preview, not the extracted folder | Right-click the ZIP, choose **Extract All**, then open the extracted folder |
| `FFmpeg and FFprobe are required` | FFmpeg is missing or not on PATH | Install FFmpeg and add its `bin` folder to PATH |
| `Missing ElevenLabs API key` | Narration is enabled but key is not set | Run `setx ELEVENLABS_API_KEY "YOUR_KEY"`, then reopen and rerun |
| `Could not find ElevenLabs voice named Victoria Voice` | Voice name differs in ElevenLabs | Paste the actual ElevenLabs voice ID into `config.json` |
| Only one lesson is detected | The script headings were not recognized | Use `Lesson 2.1: Lesson Title` format |
| Narration cost is repeated | `overwrite_existing_audio` is set to true | Keep it false unless the script changed |
| Wrong module runs | The active script was not changed | Use `RUN_MODULE.bat`, choose the module number, and confirm `CURRENT_MODULE.txt` |
| Editable PPTX files are missing | Setup did not install the PowerPoint export dependency | Run `SETUP_WINDOWS.bat` again, then rerun `RUN_ME.bat` or `RUN_MODULE.bat` |

## 11. Cost-Control Rules

The expensive step is narration generation. Slide rendering, tracker creation, Moodle descriptions, and MP4 assembly are local computer work. This package starts with `elevenlabs.enabled` set to `false`, so the first run verifies the course assets before any narration cost occurs.

When narration is enabled later, keep `overwrite_existing_audio` set to `false` so existing MP3 files are reused during reruns. Only delete or overwrite MP3 files when the narration script has changed.

> **Best practice:** Review and finalize scripts before running narration. A changed script means a new ElevenLabs narration file should be generated.

## References

[1]: https://www.python.org/downloads/release/python-31210/ "Python 3.12.10 Release"
[2]: https://ffmpeg.org/download.html "Download FFmpeg"
[3]: https://support.google.com/drive/answer/10838124 "Use Google Drive for desktop"
[4]: https://elevenlabs.io/docs/api-reference/text-to-speech/convert "ElevenLabs API Reference: Text to Speech"
