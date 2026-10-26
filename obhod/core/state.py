"""Настройки пользователя в data/state.json: ключи, регион, режим, выбранные стратегии."""
import json
import os
from dataclasses import asdict, dataclass, field

from .engine import DATA

PATH = os.path.join(DATA, "state.json")


@dataclass
class State:
    region: str = "auto"                 # auto или код из regions.json
    mode: str = ""                       # пусто — режим по умолчанию для региона
    keys: list = field(default_factory=list)          # [{"name", "uri", "outbound", "sub"}]
    selected_key: int = 0
    strategies: dict = field(default_factory=dict)    # регион -> id стратегии ByeDPI
    tun: bool = False
    dpi_all: bool = False
    connect_on_start: bool = False
    tray_hint_shown: bool = False

    @classmethod
    def load(cls):
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self):
        os.makedirs(DATA, exist_ok=True)
        tmp = PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, PATH)

    def current_key(self):
        if 0 <= self.selected_key < len(self.keys):
            return self.keys[self.selected_key]
        return None
