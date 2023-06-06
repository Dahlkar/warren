import logging

import click

from uservice.runner import ServiceRunner
from uservice.supervisors import ChangeReloader, Multiprocess


logger = logging.getLogger('uservice')


@click.command()
@click.argument("service")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
@click.option(
    "--workers",
    default=1,
    type=int,
    show_default=True,
    help="Number of worker processes. Not valid with --reload"
)
def run(
        service: str,
        *,
        reload: bool,
        workers: int,
):

    if workers > 1 and reload:
        logger.warning(
            "Can not have --reload and more than 1 workers at the same time."
        )

    runner = ServiceRunner(service_str=service)

    if reload:
        ChangeReloader(runner.run).run()

    else:
        Multiprocess(runner.run, workers).run()
