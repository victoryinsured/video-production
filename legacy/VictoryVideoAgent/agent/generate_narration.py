from pipeline import ensure_dirs, load_config, extract_scripts, generate_narration

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    lessons = extract_scripts(cfg)
    generate_narration(cfg, lessons)
