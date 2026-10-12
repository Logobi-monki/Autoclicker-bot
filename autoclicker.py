"""autoclicker.py

Improved version with:
- clean threading using Events (start/pause/stop) to avoid busy loops.
- global hotkeys for instant on/off control.
- emergency kill switch.
- configurable click interval.
- structured object-oriented code.

Usage: launch the script, press Ctrl+. to toggle the autoclicker on/off, and Esc to kill it immediately.
"""

import logging
import os
import threading
import time

from pynput.keyboard import GlobalHotKeys
from pynput.mouse import Button, Controller

# Configuration (editable)
DEFAULT_INTERVAL = 0.0  # seconds between clicks; 0.0 = as fast as possible
DEFAULT_BUTTON = Button.left
TURN_ON_KEYS = "<ctrl>+."
TURN_OFF_KEYS = "<ctrl>+,"
KILL_KEYS = "<esc>"  # emergency kill switch

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


class AutoClicker:
    """Autoclicker managed by a dedicated worker thread."""

    def __init__(self, interval: float = DEFAULT_INTERVAL, button: Button = DEFAULT_BUTTON):
        self.interval = max(0.0, float(interval))
        self.button = button
        self.mouse = Controller()

        self._running = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._worker,
            name="AutoClickerThread",
            daemon=True,
        )

    def start(self):
        """Start the worker thread if it is not already running."""
        if not self._thread.is_alive():
            logging.info("Starting autoclicker thread (interval=%s s)", self.interval)
            self._thread.start()

    def _worker(self):
        """Main click loop that respects start/stop events."""
        while not self._stop.is_set():
            if self._running.is_set():
                self._perform_click()

                if self.interval > 0.0:
                    if self._stop.wait(self.interval):
                        break
                else:
                    time.sleep(0)
            else:
                if self._stop.wait(0.1):
                    break

        logging.info("Autoclicker thread stopped")

    def _perform_click(self):
        """Perform a single mouse click with minimal overhead."""
        try:
            self.mouse.press(self.button)
            self.mouse.release(self.button)
        except Exception:
            logging.exception("Mouse click failed")

    def toggle(self):
        """Toggle the clicker on/off."""
        if self._running.is_set():
            self.pause()
        else:
            self.resume()

    def pause(self):
        """Pause the clicker without ending the thread."""
        if self._running.is_set():
            self._running.clear()
            logging.info("Autoclicker paused")

    def resume(self):
        """Resume the clicker."""
        if not self._running.is_set():
            self._running.set()
            logging.info("Autoclicker running")

    def stop(self, join_timeout: float = 1.0):
        """Request a clean shutdown and wait for the thread to exit."""
        logging.info("Shutdown requested for autoclicker")
        self._stop.set()
        self._running.set()
        if self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

    @property
    def is_running(self) -> bool:
        return self._running.is_set()


def main():
    clicker = AutoClicker(interval=DEFAULT_INTERVAL, button=DEFAULT_BUTTON)
    clicker.start()

    def _turn_on():
        clicker.resume()

    def _turn_off():
        clicker.pause()

    def _kill():
        logging.warning("Kill switch detected — stopping immediately")
        try:
            clicker.stop()
        finally:
            os._exit(0)

    hotkey_map = {
        TURN_ON_KEYS: _turn_on,
        TURN_OFF_KEYS: _turn_off,
        KILL_KEYS: _kill,
    }

    logging.info(
        "Shortcuts available: %s (turn on), %s (turn off), %s (kill)",
        TURN_ON_KEYS,
        TURN_OFF_KEYS,
        KILL_KEYS,
    )

    with GlobalHotKeys(hotkey_map) as hotkeys:
        try:
            hotkeys.join()
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt detected, shutting down cleanly...")
            clicker.stop()


if __name__ == "__main__":
    main()
