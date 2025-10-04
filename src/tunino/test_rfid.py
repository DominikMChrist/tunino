"""
Run this script to check RFID reader connection and to get RFID tag number for new RFID tags.
Usage: `uv run test_rfid.py`
"""

from mfrc522 import SimpleMFRC522

if __name__ == "__main__":
    reader = SimpleMFRC522()
    print("Hold tag to the reader")
    id, text = reader.read()
    print(f"ID: {id}\nText: {text}")
