"""
Run this script to check push buttonts are connected to the GPIO pin you expect.
Usage: `uv run test_gpio.py`
"""

import click
from gpiozero import Button


@click.command()
@click.option("--pin", "-p", default=16, help="GPIO pin number to use for the button.")
def main(pin):
    """Wait for a button press on the specified GPIO pin."""
    button = Button(pin)
    try:
        print(f"Press button on GPIO pin {pin}")
        button.wait_for_press()
        print("Pressed!")
    finally:
        button.close()


if __name__ == "__main__":
    main()
