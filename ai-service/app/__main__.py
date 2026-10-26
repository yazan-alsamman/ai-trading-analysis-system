from app.cli import main

if __name__ == "__main__":  # worker processes re-import this module on Windows
    raise SystemExit(main())
