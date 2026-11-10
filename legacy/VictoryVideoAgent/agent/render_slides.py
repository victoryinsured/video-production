from pipeline import ensure_dirs, load_config, extract_scripts, render_slides

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    lessons = extract_scripts(cfg)
    render_slides(cfg, lessons)
