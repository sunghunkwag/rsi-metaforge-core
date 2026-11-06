"""Synthetic workers for the watchdog red-team test (R3b). Spawned, so module-level."""
import time


def hog(megabytes: int, seconds: float = 20.0) -> None:
    block = bytearray(megabytes * 1024 * 1024)
    for offset in range(0, len(block), 4096):      # touch every page so it is resident
        block[offset] = 1
    time.sleep(seconds)


def small(seconds: float = 1.0) -> None:
    time.sleep(seconds)
