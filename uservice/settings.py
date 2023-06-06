from functools import lru_cache
from typing import Optional
from pydantic import BaseSettings, AmqpDsn, Field, BaseModel


class AmqpSettings(BaseModel):
    url: AmqpDsn = 'amqp://guest:guest@localhost:5672/'
    host: Optional[str]
    port: Optional[int]
    user: Optional[str]
    password: Optional[str]
    tls: bool = False
    rpc_exchange: str = 'uservice-rpc'

    def get_url(self):
        if (
                self.host or
                self.port or
                self.user or
                self.password
        ):
            protocol = 'amqps' if self.tls else 'amqp'
            return f'{protocol}://{self.user}:{self.password}@{self.host}:{self.port}'

        return self.url


class AsyncAPISettings(BaseModel):
    version: str = '2.6.0'
    title: Optional[str]
    description: str = 'My Service'


class Settings(BaseSettings):
    communication_backend: str = 'amqp'
    amqp: AmqpSettings = AmqpSettings()
    asyncapi: AsyncAPISettings = AsyncAPISettings()

    class Config:
        env_nested_delimiter = '__'


@lru_cache()
def get_settings() -> Settings:
    return Settings()
