from pipeline import ensure_dirs, load_config, upload_to_drive, OUTPUT

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    upload_to_drive(cfg, OUTPUT / "review_package")
