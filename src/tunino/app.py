import importlib.resources as pkg_resources
import os
import time
from concurrent.futures import ThreadPoolExecutor

from gpiozero import Button
from loguru import logger
from mfrc522 import SimpleMFRC522
from mpd import MPDClient

import tunino
from tunino.config import settings


def play_pause_button_task(button_number: int, mpd_client: MPDClient):
    """Event handler for Play/Pause button that runs polling loop to check if button is pressed.

    Args:
        button_number: GPIO pin number for button
        mpd_client: MPD connection
    """
    logger.info(f"Setting up play/pause button with number: {button_number}")
    button = Button(button_number)
    while True:
        try:
            button.wait_for_press()
            logger.info("Play/Pause button pressed. Toggle play/pause.")
            mpd_client.pause()
        except Exception as e:
            logger.warning(f"Tunino play/pause thread encountered exception: {e}")
        time.sleep(1)


def volume_button_task(button_number: int, change: int, mpd_client: MPDClient):
    """Event handler for either Vol Up or Vol Down button that runs polling loop to check if button is pressed.

    Args:
        button_number: GPIO pin number for button
        change: Increment for volume change. If negative, volume goes down. If positive, volume goes up.
        mpd_client: MPD connection
    """
    logger.info(f"Setting up volume button with number: {button_number}")
    button = Button(button_number)
    while True:
        try:
            button.wait_for_press()
            logger.info(f"Volume change button pressed. Change volume by {change}.")
            status = mpd_client.status()
            current_volume = int(status.get("volume", 0))
            new_volume = max(min(current_volume + change, 100), 0)
            logger.info(f"Old volume {current_volume}, new volume {new_volume}")
            mpd_client.setvol(new_volume)
        except Exception as e:
            logger.warning(f"Tunino volume change thread encountered exception: {e}")
        time.sleep(0.2)


def poweroff_button_task(button_number: int, mpd_client: MPDClient):
    """Event handler for Poweroff button that runs polling loop to check if button is pressed.

    Args:
        button_number: GPIO pin number for button
        mpd_client: MPD connection (needed to stop player and play shutdown sound instead).
    """
    logger.info(f"Setting up poweroff button with number: {button_number}")
    button = Button(button_number)

    while True:
        # Implementing hold_time manually because the built-in function from gpiozero had side-effecs on RFID reader.
        button.wait_for_press()
        start_time = time.time()
        while button.is_pressed:
            current_time = time.time()
            elapsed_time = current_time - start_time
            if elapsed_time >= 10:
                logger.info("Poweroff button (long) pressed. Shutting down.")
                mpd_client.pause()  # Have to stop player first to free up sound device
                play_sound("shutdown_sound.wav")
                time.sleep(3)  # Leave some time to play sound before power to speakers is cut.
                os.system("poweroff")
        time.sleep(1)


def rfid_task(mpd_client: MPDClient):
    """Event handler for RFID reader that waits for tag being read and then plays associated file.

    Args:
        mpd_client: MPD connection.
    """
    logger.info("Setting up RFID reader task.")
    reader = SimpleMFRC522()
    reverse_rfid_map = {v: k for k, v in settings.rfid_map.items()}
    while True:
        try:
            id, _ = reader.read()
            logger.info(f"RFID read: {id}")
            songname = settings.mpd[reverse_rfid_map[str(id)]]
            logger.info(f"MPD status {mpd_client.status()}")
            if mpd_client.status()["state"] != "play":
                logger.info(f"Playing song: {songname}")

                mpd_client.clear()  # optional: clear current playlist
                mpd_client.add(songname)
                mpd_client.play(0)
            else:
                logger.info(f"Player already busy playing. Not playing song: {songname}")

        except Exception as e:
            logger.warning(f"Tunino RFID thread encountered exception: {e}")

        time.sleep(1)


def mpd_keepalive(mpd_client: MPDClient):
    """MPD connection times out after about 60s. This function polls the MPD client repeatedly to keep connetion alive.

    Args:
        mpd_client: MPD client to be kept connected.
    """
    while True:
        try:
            mpd_client.status()
        except Exception as e:
            logger.warning(f"MPD keepalive encountered exception {e}")
            logger.info("Reconnecting MPD")
            mpd_client.disconnect()
            mpd_client.connect("localhost", 6600)
            logger.info("Connected to MPD:", mpd_client.mpd_version)
        time.sleep(50)


def init_mpd() -> MPDClient:
    """Initialise MPD client connection.

    Returns:
        MPDClient: Conncetion object.
    """
    mpd_client = MPDClient()
    mpd_client.connect("localhost", 6600)
    logger.info("Connected to MPD:", mpd_client.mpd_version)
    initial_volume = settings["initial_volume"]
    logger.info(f"Setting initial volume to {initial_volume}")
    mpd_client.setvol(initial_volume)
    return mpd_client


def play_sound(filename: str):
    """Helper function to play startup/shutdown sound.

    Args:
        filename: Name of WAV file to play. Must be located in tunino/assets/
    """
    with pkg_resources.path(tunino, f"../../assets/{filename}") as sound_file_path:
        sound_device = settings["sound_device"]
        sound_volume = settings["sound_volume"]
        # Playing a sound  in root process is a bit tricky without DBUS or PulseAudio available. Use aplay.
        os.system(f"sox -v {sound_volume} {sound_file_path} -t wav - | aplay -D {sound_device}")


def main():
    mpd_client = init_mpd()

    # Event handlers are all blocking, so run them independently inside threads
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.submit(play_pause_button_task, settings["play_pause_button_pin"], mpd_client=mpd_client)
        executor.submit(volume_button_task, settings["volume_up_button_pin"], change=5, mpd_client=mpd_client)
        executor.submit(volume_button_task, settings["volume_down_button_pin"], change=-5, mpd_client=mpd_client)
        executor.submit(poweroff_button_task, settings["poweroff_button_pin"], mpd_client=mpd_client)
        executor.submit(rfid_task, mpd_client=mpd_client)
        executor.submit(mpd_keepalive, mpd_client=mpd_client)

        # Make a noise that startup is completed
        logger.info("All threads started. Ready to go.")
        play_sound("startup_sound.wav")


if __name__ == "__main__":
    main()
