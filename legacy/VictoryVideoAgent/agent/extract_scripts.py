from pipeline import ensure_dirs, load_config, extract_scripts

if __name__ == "__main__":
    ensure_dirs()
    extract_scripts(load_config())
