"""Run this project without mafx:  uv run python -m hello_world [target] [-p "prompt"]."""

from maf_labs_host import run_project


def main() -> None:
    run_project(__file__)


if __name__ == "__main__":
    main()
