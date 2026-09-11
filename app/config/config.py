from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ..db import Store
from ..models import SeedPreference

MIN_PUBLISH_INTERVAL_HOURS = 24


@dataclass
class Config:
    stremhu_data_dir: str = "/stremhu"

    torbox_api_key: str = ""

    push_enabled: bool = True
    push_interval_minutes: int = 15
    lookback_hours: int = 48
    min_fetched_fraction: float = 0.5
    seed_preference: int = SeedPreference.ALWAYS

    push_limit: int = 10
    max_torrent_size_gb: float = 0.0

    publish_enabled: bool = False
    publish_interval_hours: int = 24

    @property
    def database_path(self) -> Path:
        return Path(self.stremhu_data_dir) / "system" / "database" / "app.db"

    @property
    def downloads_path(self) -> Path:
        return Path(self.stremhu_data_dir) / "downloads"

    @property
    def min_fetched_percent(self) -> int:
        return round(self.min_fetched_fraction * 100)

    @property
    def effective_publish_interval_hours(self) -> int:
        return max(MIN_PUBLISH_INTERVAL_HOURS, self.publish_interval_hours)

    @property
    def max_torrent_size_bytes(self) -> int | None:
        if self.max_torrent_size_gb <= 0:
            return None
        return int(self.max_torrent_size_gb * 1_000_000_000)


def load(store: Store) -> Config:
    known = {f.name for f in fields(Config)}
    stored = {k: v for k, v in store.config.values().items() if k in known}
    return Config(**stored)


def save(store: Store, cfg: Config) -> None:
    store.config.save(asdict(cfg))
