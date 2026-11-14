"""`python -m earth_jukebox` -> run the web app on http://127.0.0.1:8000."""

from __future__ import annotations

import uvicorn

from earth_jukebox.bootstrap import build_app


def main() -> None:
    uvicorn.run(build_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
