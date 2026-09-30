"""Futbin adapter: disabled by default.

futbin.com answers 403 with a Cloudflare bot challenge to plain HTTP clients. We do not
bypass that. This class keeps the DataSource shape so an allowed access path (e.g. an
official API) can be plugged in later; until then it yields nothing.
"""
from typing import Iterator

from .base import League, NormalizedPlayer


class FutbinSource:
    name = "futbin"

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def leagues(self) -> list[League]:
        return []

    def players(self) -> Iterator[NormalizedPlayer]:
        if self.enabled:
            raise NotImplementedError("No permitted Futbin access path is configured")
        return iter(())
