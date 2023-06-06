import logging
import click

from .subprocess import Supervisor, get_subprocess

logger = logging.getLogger('uservice')


class Multiprocess(Supervisor):
    def __init__(self, target, workers):
        super().__init__(target)
        self.workers = workers
        self.processes = []

    def startup(self) -> None:
        super().startup()
        message = "Started parent process [{}]".format(str(self.pid))
        color_message = "Started parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})

        for _idx in range(self.workers):
            process = get_subprocess(
                target=self.target,
            )
            process.start()
            logger.info(f"Started worker process [{process.pid}]")
            self.processes.append(process)

    def loop(self):
        self.should_exit.wait()

    def shutdown(self) -> None:
        for process in self.processes:
            logger.info(f"Stopping worker process [{process.pid}]")
            process.terminate()
            process.join()

        message = "Stopping parent process [{}]".format(str(self.pid))
        color_message = "Stopping parent process [{}]".format(
            click.style(str(self.pid), fg="cyan", bold=True)
        )
        logger.info(message, extra={"color_message": color_message})
