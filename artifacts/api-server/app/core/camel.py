"""Utilitários para converter chaves snake_case → camelCase nas respostas."""
import re


def _to_camel(name: str) -> str:
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _convert(obj):
    if isinstance(obj, dict):
        return {_to_camel(k): _convert(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert(item) for item in obj]
    return obj
