"""Compatibility facade for the pre-split application bundle."""

from pathlib import Path

from msys_sdk.tk_app import *  # noqa: F401,F403
from msys_sdk.tk_app import TouchApplication as _SdkTouchApplication


_ICON_DIR = Path(__file__).resolve().parents[2] / "share" / "icons"


class TouchApplication(_SdkTouchApplication):
    """Retain the legacy bundle's package-relative icon lookup."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("icon_dir", _ICON_DIR)
        super().__init__(*args, **kwargs)
