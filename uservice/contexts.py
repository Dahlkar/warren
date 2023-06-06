#!/usr/bin/env python3
from pydantic import BaseSettings


class ServiceContext:
    def __init__(
            self,
            name: str,
            settings: BaseSettings,
    ):
        self.name = name
        self.settings = settings
