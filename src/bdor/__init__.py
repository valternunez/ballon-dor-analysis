"""bdor — Ballon d'Or Hype vs. Merit analysis package.

See PROJECT_NOTES.md for the locked methodology and docs/windowing.md for the
per-year performance/hype windows.
"""

import logging

__version__ = "0.1.0"


class _SoccerdataInfoFilter(logging.Filter):
    """Drop soccerdata's sub-WARNING config notices.

    soccerdata logs them via the root logger with ``basicConfig(force=True)``, so pre-setting its
    logger level doesn't hold — a root-logger filter does, and only touches its own records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return not (record.levelno < logging.WARNING
                    and "soccerdata" in record.pathname.replace("\\", "/"))


def _quiet_noisy_imports() -> None:
    """Keep harmless third-party import chatter out of the terminal.

    arviz/matplotlib (backend/namespace notices) and pytensor (its expected "g++ not available" —
    we use nutpie, no C compiler) log INFO/WARNING at import; a level bump silences them. soccerdata
    needs the filter above. Genuine errors (>= ERROR) still surface, and our own loggers
    (e.g. bdor.data.gdelt) are untouched.
    """
    for name in ("arviz", "arviz_base", "arviz_stats", "arviz_plots", "matplotlib"):
        logging.getLogger(name).setLevel(logging.WARNING)  # drop INFO
    logging.getLogger("pytensor").setLevel(logging.ERROR)  # also hides the expected g++ warning
    logging.getLogger().addFilter(_SoccerdataInfoFilter())


_quiet_noisy_imports()
