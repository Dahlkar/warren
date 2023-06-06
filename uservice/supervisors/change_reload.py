import logging
import os
import threading
import signal
import multiprocessing

import click

from pathlib import Path
from typing import Optional, List
from watchfiles import watch, PythonFilter
from .subprocess import get_subprocess, Supervisor


logger = logging.getLogger('uservice')


class ChangeReloader(Supervisor):
    def __init__(self, target, reload_dirs = None):
        super().__init__(target)
        if reload_dirs is None:
            self.reload_dirs = [Path(os.getcwd()).cwd()]
        else:
            self.reload_dirs = reload_dirs
        self.watcher = watch(
            *self.reload_dirs,
            watch_filter=PythonFilter(),
            stop_event=self.should_exit,
            yield_on_timeout=True,
        )
        self.reloader_name = "ChangeReloader"

    def loop(self):
        for changes in self:
            if changes:
                logger.warning(
                    "%s detected changes in %s. Reloading...",
                    self.reloader_name,
                    ", ".join(map(_display_path, changes)),
                )
                self.restart()

    def __iter__(self):
        return self

    def __next__(self) -> Optional[List[Path]]:
        return self.should_restart()

    def startup(self) -> None:
        super().startup()
        message = f"Started reloader process [{self.pid}] using {self.reloader_name}"
        color_message = "Started reloader process [{}] using {}".format(
            click.style(str(self.pid), fg="cyan", bold=True),
            click.style(str(self.reloader_name), fg="cyan", bold=True),
        )
        logger.info(message, extra={"color_message": color_message})
        self.start_process()

    def should_restart(self) -> Optional[List[Path]]:
        self.pause()
        changes = next(self.watcher)
        if changes:
            return {Path(c[1]) for c in changes}

        return None

    def restart(self) -> None:
        self.process.terminate()
        self.process.join()
        self.start_process()

    def start_process(self):
        self.process = get_subprocess(self.target)
        self.process.start()

    def pause(self) -> None:
        if self.should_exit.wait(0.25):
            raise StopIteration()

    def shutdown(self) -> None:
        self.process.terminate()  # pragma: py-win32
        self.process.join()

        message = "Stopping reloader process [{}]".format(str(self.pid))
        color_message = "Stopping reloader process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})


def _display_path(path: Path) -> str:
    try:
        return f"'{path.relative_to(Path.cwd())}'"
    except ValueError:
        return f"'{path}'"
