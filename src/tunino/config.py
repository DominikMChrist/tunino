"""
Reads Dynaconf config file.
Added complications:
* Have .secrets.json for config that is not part of git repo
* Read location of MPD music directory and read json config from that directory
"""

import json
import os
import sys
from pathlib import Path

from dynaconf import Dynaconf
from loguru import logger


def get_mpd_music_directory(conf_path="/etc/mpd.conf"):
    music_dir = None
    with open(conf_path) as f:
        for line in f:
            if line.strip().startswith("music_directory"):
                # Extract value between quotes
                music_dir = line.split('"')[1]
                break
    if music_dir and music_dir.startswith("~"):
        music_dir = os.path.expanduser(music_dir)
    return Path(music_dir) if music_dir else None


settings = Dynaconf(
    environments=True,
    env="development",
    # `settings_files` = Load these files in the order.
    settings_files=["settings.json", ".secrets.json"],
)

# Load mpd-level settings as subtree in config
mpd_config_path = get_mpd_music_directory() / "rfid_song_map.json"
with open(mpd_config_path) as f:
    mpd_config = json.load(f)
settings.set("mpd", mpd_config)

log_level = settings["log_level"]
logger.remove()
print("Logging to stdout at level:", log_level)
logger.add(sys.stdout, level=log_level)
