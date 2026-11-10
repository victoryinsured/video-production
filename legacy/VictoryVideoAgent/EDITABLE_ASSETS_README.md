# Editable Assets Guide

Author: **Manus AI**  
Version: **Included in Windows Local Package v1.3**  
Date: **2026-06-08**

This package now creates a reusable editing folder every time the agent runs. The normal MP4 video is still created when narration audio and FFmpeg are available, but you also get source assets that are easier to edit later in Canva, PowerPoint, or another video editor.

## Where to Find the Editable Assets

After a successful run, open this folder:

```text
output\review_package\editable_assets
```

The same assets are also stored in:

```text
output\editable_assets
```

Each lesson receives its own folder. The lesson folder is designed so you can make small future edits without needing the agent rebuilt.

| File or Folder | Purpose |
|---|---|
| `editable_slides.pptx` | Editable PowerPoint deck that can be opened in PowerPoint or uploaded to Canva |
| `rendered_slides` | Exact slide PNG images used in the video |
| `script` | Exact narration text for that lesson |
| `audio` | MP3 narration when narration was enabled or already existed |
| `video` | Finished MP4 video when FFmpeg assembled it successfully |
| `slide_text.csv` | Slide-by-slide text map for easier editing and review |
| `edit_notes.md` | Plain-English notes explaining what to edit and which files to use |

## Recommended Canva Workflow

For quick edits, upload the finished MP4 to Canva. This is best for trimming, splitting, adding captions, adding a logo, placing text over the video, or adding music.

For deeper edits, upload `editable_slides.pptx` to Canva. This gives you a more editable starting point than the flattened MP4. After editing the slides, you can combine the edited visuals with the lesson MP3 narration from the `audio` folder.

| Editing Goal | Best Asset |
|---|---|
| Trim or caption the final lesson | MP4 file in `video` |
| Change visible slide wording | `editable_slides.pptx` |
| Add a new branded intro or outro | MP4 plus Canva overlay/introduction |
| Reuse narration without paying again | MP3 file in `audio` |
| Rebuild visual timing manually | PNG slides plus `slide_text.csv` |

## Important Note

The finished MP4 is still a flattened video. Canva can edit the MP4 as a video, but it usually cannot turn the text already burned into the MP4 back into live text boxes. That is why this package also creates PPTX decks, PNG slide images, scripts, audio copies, and edit notes.
