"""CLI entry point: one JSON job file in, one JSON result on stdout, per invocation.

Called by the Node job-queue worker (see server/src/queue/handlers.ts) as a short-lived
subprocess per pipeline step — this engine is never a long-running service. Usage:

    python -m victory_engine.cli <job.json>

The job file's "step" field selects the handler. Every handler returns a plain JSON-serializable
dict; on success it is printed to stdout and the process exits 0. On failure, a dict of the shape
{"error": "<message>"} is printed to stdout and the process exits 1, so the caller can always
`JSON.parse(stdout)` regardless of outcome.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

from .brand import brand_from_dict
from .editable_assets import build_editable_deck
from .moodle_text import lesson_description_html, module_description_html
from .narration import synthesize_narration, probe_audio_duration
from .parser import ParsedLesson, ParsedResource, parse_curriculum, title_from_filename_str
from .readers import read_paragraphs
from .render import SlideSpec, make_slide_specs, render_lesson_slides
from .video import assemble_video


def _lesson_from_dict(data: Dict[str, Any]) -> ParsedLesson:
    lesson = ParsedLesson(
        number=data.get("number", ""),
        order=data.get("order"),
        title=data.get("title", "Untitled Lesson"),
        lesson_type=data.get("lessonType", data.get("lesson_type", "video")),
        description=data.get("description", ""),
        video_description=data.get("videoDescription", data.get("video_description", "")),
        script_lines=data.get("scriptLines", data.get("script_lines")) or (
            [data["scriptText"]] if data.get("scriptText") else []
        ),
        knowledge_checks=data.get("knowledgeChecks", data.get("knowledge_checks", [])) or [],
        production_instructions=data.get("productionInstructions", data.get("production_instructions", "")),
        tags=data.get("tags", []) or [],
    )
    for r in data.get("resources", []) or []:
        lesson.resources.append(ParsedResource(
            title=r.get("title", "Resource"),
            description=r.get("description", ""),
            instructions=r.get("instructions", ""),
            filename=r.get("filename", ""),
            resource_type=r.get("resourceType", r.get("resource_type", "file")),
        ))
    return lesson


def _slide_spec_from_dict(data: Dict[str, Any]) -> SlideSpec:
    return SlideSpec(
        kind=data["kind"],
        heading=data.get("heading", ""),
        subheading=data.get("subheading", ""),
        body=data.get("body", ""),
        bullets=data.get("bullets", []) or [],
        left_label=data.get("leftLabel", data.get("left_label", "")),
        right_label=data.get("rightLabel", data.get("right_label", "")),
        left_points=data.get("leftPoints", data.get("left_points", [])) or [],
        right_points=data.get("rightPoints", data.get("right_points", [])) or [],
        steps=data.get("steps", []) or [],
        quote=data.get("quote", ""),
        attribution=data.get("attribution", ""),
    )


def _slide_spec_to_dict(spec: SlideSpec) -> Dict[str, Any]:
    return {
        "kind": spec.kind, "heading": spec.heading, "subheading": spec.subheading, "body": spec.body,
        "bullets": spec.bullets, "leftLabel": spec.left_label, "rightLabel": spec.right_label,
        "leftPoints": spec.left_points, "rightPoints": spec.right_points, "steps": spec.steps,
        "quote": spec.quote, "attribution": spec.attribution,
    }


def handle_parse_document(job: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(job["documentPath"])
    fallback_title = job.get("fallbackTitle") or title_from_filename_str(path.name)
    paragraphs = read_paragraphs(path)
    course = parse_curriculum(paragraphs, fallback_title=fallback_title)
    return {
        "course": {
            "title": course.title,
            "description": course.description,
            "modules": [
                {
                    "number": m.number,
                    "title": m.title,
                    "description": m.description,
                    "lessons": [
                        {
                            "number": l.number,
                            "order": l.order,
                            "title": l.title,
                            "lessonType": l.lesson_type,
                            "description": l.description,
                            "videoDescription": l.video_description,
                            "scriptText": l.script_text,
                            "scriptHash": l.script_hash,
                            "knowledgeChecks": l.knowledge_checks,
                            "productionInstructions": l.production_instructions,
                            "tags": l.tags,
                            "resources": [
                                {
                                    "title": r.title, "description": r.description,
                                    "instructions": r.instructions, "filename": r.filename,
                                    "resourceType": r.resource_type,
                                }
                                for r in l.resources
                            ],
                        }
                        for l in m.lessons
                    ],
                }
                for m in course.modules
            ],
        }
    }


def handle_make_slide_specs(job: Dict[str, Any]) -> Dict[str, Any]:
    lesson = _lesson_from_dict(job["lesson"])
    specs = make_slide_specs(lesson)
    return {"slideSpecs": [_slide_spec_to_dict(s) for s in specs]}


def handle_render_slides(job: Dict[str, Any]) -> Dict[str, Any]:
    lesson = _lesson_from_dict(job["lesson"])
    brand = brand_from_dict(job.get("brand"))
    output_dir = Path(job["outputDir"])
    paths = render_lesson_slides(lesson, brand, job.get("moduleTitle", ""), output_dir)
    specs = make_slide_specs(lesson)
    return {
        "slidePaths": [str(p) for p in paths],
        "slideSpecs": [_slide_spec_to_dict(s) for s in specs],
        "slideKinds": [s.kind for s in specs],
        "slideTexts": [(s.heading + " " + " ".join(s.bullets)).strip() or s.quote or s.heading for s in specs],
    }


def handle_synthesize_narration(job: Dict[str, Any]) -> Dict[str, Any]:
    output_path = Path(job["outputPath"])
    synthesize_narration(
        script_text=job["scriptText"],
        voice_ref=job["voiceRef"],
        api_key=job["apiKey"],
        output_path=output_path,
        model_id=job.get("modelId", "eleven_turbo_v2_5"),
    )
    duration = probe_audio_duration(output_path)
    return {"audioPath": str(output_path), "durationSeconds": duration}


def handle_assemble_video(job: Dict[str, Any]) -> Dict[str, Any]:
    brand = brand_from_dict(job.get("brand"))
    output_path = assemble_video(
        slide_paths=[Path(p) for p in job["slidePaths"]],
        slide_texts=job["slideTexts"],
        slide_kinds=job["slideKinds"],
        narration_path=Path(job["narrationPath"]),
        output_path=Path(job["outputPath"]),
        brand=brand,
    )
    return {"videoPath": str(output_path)}


def handle_build_editable_deck(job: Dict[str, Any]) -> Dict[str, Any]:
    brand = brand_from_dict(job.get("brand"))
    specs = [_slide_spec_from_dict(s) for s in job["slideSpecs"]]
    output_path = build_editable_deck(job.get("lessonTitle", ""), specs, brand, Path(job["outputPath"]))
    return {"deckPath": str(output_path)}


def handle_moodle_description(job: Dict[str, Any]) -> Dict[str, Any]:
    if "lesson" in job:
        lesson = _lesson_from_dict(job["lesson"])
        return {"html": lesson_description_html(lesson)}
    return {"html": module_description_html(job.get("moduleTitle", ""), job.get("moduleDescription", ""))}


_HANDLERS = {
    "parse_document": handle_parse_document,
    "make_slide_specs": handle_make_slide_specs,
    "render_slides": handle_render_slides,
    "synthesize_narration": handle_synthesize_narration,
    "assemble_video": handle_assemble_video,
    "build_editable_deck": handle_build_editable_deck,
    "moodle_description": handle_moodle_description,
}


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(json.dumps({"error": "Usage: python -m victory_engine.cli <job.json>"}))
        return 1

    job_path = Path(argv[1])
    try:
        job = json.loads(job_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"error": f"Could not read job file: {exc}"}))
        return 1

    step = job.get("step")
    handler = _HANDLERS.get(step)
    if handler is None:
        print(json.dumps({"error": f"Unknown step: {step!r}. Known steps: {sorted(_HANDLERS)}"}))
        return 1

    try:
        result = handler(job)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "traceback": traceback.format_exc()}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
