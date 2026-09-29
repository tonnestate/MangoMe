from __future__ import annotations

from .cli import main as _cli_main


def main() -> None:
    """Run the normal CLI with the seven-tool managed worker surface."""
    _cli_main(surface="worker")


if __name__ == "__main__":
    main()
