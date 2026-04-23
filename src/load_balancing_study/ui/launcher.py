from pathlib import Path
import sys


def main() -> int:
    try:
        from streamlit.web import cli as streamlit_cli
    except ModuleNotFoundError as exc:
        raise SystemExit("streamlit is required to launch the UI") from exc

    app_path = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app_path), *sys.argv[1:]]
    return streamlit_cli.main()


if __name__ == "__main__":
    raise SystemExit(main())