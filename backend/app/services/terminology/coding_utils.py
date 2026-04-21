from collections.abc import Iterable


def coding_displays(codings: Iterable[dict[str, str]]) -> list[str]:
    return [coding["display"] for coding in codings if coding.get("display")]

