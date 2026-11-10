from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
MODULE_SCRIPTS = ROOT / "module_scripts"
INPUT = ROOT / "input_scripts"
CONFIG_PATH = ROOT / "config" / "config.json"

DEFAULT_MODULE_NAMES: Dict[int, str] = {
    1: "The Victory Framework Foundation",
    2: "The Engine — Getting Answers to What You Don't Know",
    3: "Victory Framework Module 3",
    4: "Victory Framework Module 4",
    5: "Victory Framework Module 5",
    6: "Victory Framework Module 6",
    7: "Victory Framework Module 7",
    8: "Victory Framework Module 8",
    9: "Victory Framework Module 9",
    10: "Victory Framework Module 10",
    11: "Victory Framework Module 11",
    12: "Victory Framework Module 12",
    13: "Victory Framework Module 13",
    14: "Victory Framework Module 14",
    15: "Victory Framework Module 15",
}


def available_modules() -> Dict[int, Path]:
    modules: Dict[int, Path] = {}
    for path in MODULE_SCRIPTS.glob("victory-framework-module*-scripts.docx"):
        match = re.search(r"module(\d+)-scripts", path.name, flags=re.IGNORECASE)
        if match:
            modules[int(match.group(1))] = path
    return dict(sorted(modules.items()))


def read_docx_paragraphs(path: Path) -> list[str]:
    try:
        from docx import Document
    except Exception:
        return []
    try:
        doc = Document(str(path))
    except Exception:
        return []
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def clean_module_title(value: str, module_number: int) -> str:
    value = value.strip().strip("-–—:").strip()
    value = re.sub(r"^module\s+\d+\s*[:\-–—]?\s*", "", value, flags=re.IGNORECASE).strip()
    return value or DEFAULT_MODULE_NAMES.get(module_number, f"Victory Framework Module {module_number}")


def extract_module_name(path: Path, module_number: int) -> str:
    for paragraph in read_docx_paragraphs(path)[:80]:
        match = re.match(r"^\s*MODULE\s*:\s*(.+?)\s*$", paragraph, flags=re.IGNORECASE)
        if match:
            return clean_module_title(match.group(1), module_number)
    return DEFAULT_MODULE_NAMES.get(module_number, f"Victory Framework Module {module_number}")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def clear_active_inputs() -> None:
    INPUT.mkdir(parents=True, exist_ok=True)
    for path in INPUT.iterdir():
        if path.is_file() and path.suffix.lower() in {".docx", ".txt"}:
            path.unlink()


def select_module(module_number: int) -> Path:
    modules = available_modules()
    if module_number not in modules:
        available = ", ".join(str(n) for n in modules) or "none"
        raise FileNotFoundError(f"Module {module_number} script was not found in {MODULE_SCRIPTS}. Available modules: {available}.")

    source = modules[module_number]
    module_name = extract_module_name(source, module_number)
    clear_active_inputs()
    target = INPUT / source.name
    shutil.copy2(source, target)

    config = load_config()
    config["course_name"] = config.get("course_name", "Victory Framework")
    config["module_number"] = module_number
    config["module_name"] = module_name
    config["input_pattern"] = "*.docx"
    config["treat_lesson_headings_as_metadata"] = True
    config.setdefault("elevenlabs", {})["enabled"] = bool(config.get("elevenlabs", {}).get("enabled", False))
    save_config(config)

    status = ROOT / "CURRENT_MODULE.txt"
    status.write_text(
        f"Current active module: Module {module_number}\n"
        f"Module title: {module_name}\n"
        f"Active script: input_scripts/{target.name}\n"
        f"Source script: module_scripts/{source.name}\n",
        encoding="utf-8",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Select the Victory Framework module to process.")
    parser.add_argument("module", nargs="?", type=int, help="Module number to activate, such as 3 or 15.")
    parser.add_argument("--list", action="store_true", help="List available modules and exit.")
    args = parser.parse_args()

    modules = available_modules()
    if args.list:
        print("Available module scripts:")
        for number, path in modules.items():
            print(f"  Module {number}: {path.name} — {extract_module_name(path, number)}")
        return

    module_number = args.module
    if module_number is None:
        print("Available modules:", ", ".join(str(n) for n in modules) or "none")
        raw = input("Enter the module number to run: ").strip()
        try:
            module_number = int(raw)
        except ValueError:
            print(f"ERROR: {raw!r} is not a valid module number.")
            sys.exit(1)

    try:
        active = select_module(module_number)
    except Exception as exc:
        print("ERROR:", exc)
        sys.exit(1)

    print(f"Selected Module {module_number}.")
    print(f"Active script copied to: {active.relative_to(ROOT)}")
    print("Configuration updated. You can now run RUN_ME.bat, or use RUN_MODULE.bat to run immediately.")


if __name__ == "__main__":
    main()
