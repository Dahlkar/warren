import sys
import os
import multiprocessing
import threading
import signal
from typing import Optional

spawn = multiprocessing.get_context("spawn")

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


class Supervisor:
    def __init__(self, target):
        self.target = target
        self.pid = os.getpid()
        self.should_exit = threading.Event()

    def signal_handler(self, sig, frame) -> None:
        self.should_exit.set()

    def run(self):
        self.startup()
        self.loop()
        self.shutdown()

    def startup(self):
        for sig in HANDLED_SIGNALS:
            signal.signal(sig, self.signal_handler)

    def shutdown(self):
        raise NotImplementedError


def get_subprocess(target):
    stdin_fileno: Optional[int]
    try:
        stdin_fileno = sys.stdin.fileno()
    except OSError:
        stdin_fileno = None
    kwargs = {
        "target": target,
        "stdin_fileno": stdin_fileno,
    }
    return spawn.Process(target=subprocess_started, kwargs=kwargs)


def subprocess_started(
        target,
        stdin_fileno: Optional[int],
) -> None:
    if stdin_fileno is not None:
        sys.stdin = os.fdopen(stdin_fileno)

    target()
