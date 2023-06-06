import logging

from .cli import cli


logging.basicConfig(level=logging.INFO)


def main():
    cli()
