from pipeline import ensure_dirs, load_config, extract_scripts, generate_moodle_descriptions

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    lessons = extract_scripts(cfg)
    generate_moodle_descriptions(cfg, lessons, [])
