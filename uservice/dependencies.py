import asyncio
import functools
import inspect
from typing import Callable, Dict, List, Any, Annotated
from contextlib import asynccontextmanager, AsyncExitStack
from pydantic.typing import get_origin, get_args


class Depends:
    def __init__(self, dependency: Callable):
        self.dependency = dependency


class Dependant:
    def __init__(self, *, call: Callable):
        self.call = call
        self.params = inspect.signature(call).parameters
        self.required_params = {}
        self.dependencies = {}
        for param_name, param in self.params.items():
            if isinstance(param.default, Depends):
                call = param.default.dependency
                self.dependencies[param_name] = Dependant(call=call)

            elif (
                    param.annotation is not inspect.Signature.empty
                    and get_origin(param.annotation) is Annotated
            ):
                annotation = get_args(param.annotation)[1]
                if isinstance(annotation, Depends):
                    call = annotation.dependency
                    self.dependencies[param_name] = Dependant(call=call)
            elif param.default is inspect.Signature.empty:
                self.required_params[param_name] = param

    @property
    def name(self):
        return self.call.__name__

    async def prepare_params(self, stack: AsyncExitStack, params: Dict[str, Any]):
        _params = {}
        for param in self.required_params:
            _params[param] = params[param]

        _params.update(
            await solve_dependencies(
                stack=stack,
                params=params,
                dependencies=self.dependencies,
            )
        )
        return _params


async def solve_dependencies(
        *,
        stack: AsyncExitStack,
        params: Dict[str, Any],
        dependencies: Dict[str, Dependant],
):
    deps = {}
    for kw, dependency in dependencies.items():
        dependency_params = await dependency.prepare_params(stack, params)
        if is_async_gen_callable(dependency.call):
            cm = asynccontextmanager(dependency.call)(**dependency_params)
            deps[kw] = await stack.enter_async_context(cm)
        elif is_async_callable(dependency.call):
            deps[kw] = await dependency.call(**dependency_params)
        else:
            deps[kw] = dependency.call(**dependency_params)

    return deps


def is_async_gen_callable(obj: Any) -> bool:
    return inspect.isasyncgenfunction(obj) or inspect.isasyncgenfunction(obj.__call__)


def is_async_callable(obj: Any) -> bool:
    while isinstance(obj, functools.partial):
        obj = obj.func

    return asyncio.iscoroutinefunction(obj) or (
        callable(obj) and asyncio.iscoroutinefunction(obj.__call__)
    )
