from pipeline import ensure_dirs, load_config, extract_scripts, create_tracker

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    lessons = extract_scripts(cfg)
    create_tracker(cfg, lessons, [], [])
