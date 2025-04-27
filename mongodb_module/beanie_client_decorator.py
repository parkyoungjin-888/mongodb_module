from typing import Optional
from functools import wraps
from contextlib import asynccontextmanager
import contextvars

from mongodb_module.beanie_client import CollectionClient


collection_client_var = contextvars.ContextVar[Optional[CollectionClient]]('client_instance')


@asynccontextmanager
async def set_collection_client_context(client):
    token = collection_client_var.set(client)
    try:
        yield
    finally:
        collection_client_var.reset(token)


def with_collection_client(client_config, collection_model):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with CollectionClient(**client_config, collection_model=collection_model) as client:
                async with set_collection_client_context(client):
                    return await func(*args, **kwargs)
        return wrapper
    return decorator
