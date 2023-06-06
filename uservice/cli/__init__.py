#!/usr/bin/env python3
import click

from .run import run


@click.group()
def group():
    pass


def cli():
    group.add_command(run)
    group()
