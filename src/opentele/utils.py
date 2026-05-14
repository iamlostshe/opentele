# utils.py (OpenTele)

from __future__ import annotations

import abc
from collections.abc import Callable, Coroutine
from types import FunctionType
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

_T = TypeVar("_T")
_TCLS = TypeVar("_TCLS", bound=type)
_RT = TypeVar("_RT")
_F = TypeVar("_F", bound=Callable[..., Any])


class BaseMetaClass(abc.ABCMeta):  # pragma: no cover
    def __new__(
        cls: type[_T], clsName: str, bases: tuple[type], attrs: dict[str, Any],
    ) -> _T:

        # Hook all subclass methods
        if False:  # debug.IS_DEBUG_MODE, замените на False для упрощения
            ignore_list = [
                "__new__",
                "__del__",
                "__get__",
                "__call__",
                "__set_name__",
                "__str__",
                "__repr__",
            ]

            for attr, val in attrs.items():
                if (
                    attr not in ignore_list
                    and callable(val)
                    and not isinstance(val, type)
                ):
                    # newVal = debug.DebugMethod(val)
                    attrs[attr] = val  # Оставляем без изменений для упрощения

        result = super().__new__(cls, clsName, bases, attrs)

        return result


class BaseObject(metaclass=BaseMetaClass):
    pass


class override:  # nocov
    """To use inside a class decorated with @extend_class
    Any attributes decorated with @override will be replaced
    """

    def __new__(cls, decorated_func: _F) -> _F:

        # check if decorated_cls really is a function
        if not isinstance(decorated_func, FunctionType):
            raise TypeError(
                "@override decorator is only for functions, not classes",
            )

        decorated_func.__isOverride__ = True  # type: ignore
        return decorated_func  # type: ignore

    @staticmethod
    def isOverride(func: _F) -> bool:
        if not hasattr(func, "__isOverride__"):
            return False
        return func.__isOverride__


class extend_class:  # nocov
    """Extend a class, all attributes will be added to its parents
    This won't override attributes that are already existed, please refer to @override or @extend_override_class to do this
    """

    # Добавляем список специальных атрибутов для игнорирования
    SPECIAL_ATTRIBUTES = [
        "__firstlineno__",
        "__module__",
        "__dict__",
        "__weakref__",
        "__doc__",
        "__annotations__",  # Добавьте другие специальные атрибуты при необходимости
    ]

    def __new__(cls, decorated_cls: _TCLS, isOverride: bool = False) -> _TCLS:

        # check if decorated_cls really is a class (type)
        if not isinstance(decorated_cls, type):
            raise TypeError(
                "@extend_class decorator is only for classes, not functions",
            )

        newAttributes = dict(decorated_cls.__dict__)
        crossDelete = ["__abstractmethods__", "__module__", "_abc_impl", "__doc__"]
        [
            (newAttributes.pop(cross) if cross in newAttributes else None)
            for cross in crossDelete
        ]

        crossDelete = {}

        base = decorated_cls.__bases__[0]

        if not isOverride:
            # loop through its parents and add attributes

            for attributeName, attributeValue in newAttributes.items():

                # Игнорируем специальные атрибуты
                if attributeName.startswith("__") and attributeName.endswith("__"):
                    continue

                # check if class base already has this attribute
                result = extend_class.getattr(base, attributeName)

                if result is not None:
                    if id(result["value"]) == id(attributeValue):
                        crossDelete[attributeName] = attributeValue

                    # if not override this attribute
                    elif not override.isOverride(attributeValue):
                        print(
                            f"[{attributeName}] {id(result['value'])} - {id(attributeValue)}",
                        )
                        raise TypeError("Attribute conflict detected. Use @override to override existing attributes.")

            [newAttributes.pop(cross) for cross in crossDelete]

        for attributeName, attributeValue in newAttributes.items():

            # Игнорируем специальные атрибуты
            if attributeName.startswith("__") and attributeName.endswith("__"):
                continue

            # let's backup this attribute for future uses
            result = extend_class.getattr(base, attributeName)

            if result is not None:
                # ! dirty code, gonna fix it later, it's okay for now
                setattr(
                    base,
                    f"__{decorated_cls.__name__}__{attributeName}",
                    result["value"],
                )
                setattr(
                    decorated_cls,
                    f"__{decorated_cls.__name__}__{attributeName}",
                    result["value"],
                )

            setattr(base, attributeName, attributeValue)

        return decorated_cls

    @staticmethod
    def object_hierarchy_getattr(obj: object, attributeName: str) -> list[str]:

        results = []
        if type(obj) == object:
            return results

        if attributeName in obj.__dict__:
            val = obj.__dict__[attributeName]
            results.append({"owner": obj, "value": val})

        if attributeName in obj.__class__.__dict__:
            val = obj.__class__.__dict__[attributeName]
            results.append({"owner": obj, "value": val})

        for base in obj.__bases__:  # type: ignore
            results += extend_class.object_hierarchy_getattr(base, attributeName)

        results.reverse()
        return results

    @staticmethod
    def getattr(obj: object, attributeName: str) -> dict | None:
        try:
            value = getattr(obj, attributeName)
            return {"owner": obj, "value": value}
        except AttributeError:
            return None


class extend_override_class(extend_class):
    """Extend a class, all attributes will be added to its parents
    If those attributes are already existed, they will be replaced by the new one
    """

    def __new__(cls, decorated_cls: _TCLS) -> _TCLS:
        return super().__new__(cls, decorated_cls, True)


class sharemethod(type):
    def __get__(self, obj, cls):
        self.__owner__ = obj if obj else cls
        return self

    def __call__(self, *args) -> Any:
        return self.__fget__.__get__(self.__owner__)(*args)  # type: ignore

    def __set_name__(self, owner, name):
        self.__owner__ = owner

    def __new__(cls: type[_T], func: _F) -> type[_F]:

        clsName = func.__class__.__name__
        bases = func.__class__.__bases__
        attrs = func.__dict__
        # attrs = dict(func.__class__.__dict__)
        result = super().__new__(cls, clsName, bases, attrs)
        result.__fget__ = func

        return result
