"""Автозапуск вместе с системой: реестр Run на Windows, LaunchAgent на macOS."""
from .osinfo import MAC

if MAC:
    from .autostart_mac import NAME, command, current, disable, enable, is_enabled, refresh  # noqa: F401
else:
    from .autostart_win import NAME, RUN_KEY, command, current, disable, enable, is_enabled, refresh  # noqa: F401
