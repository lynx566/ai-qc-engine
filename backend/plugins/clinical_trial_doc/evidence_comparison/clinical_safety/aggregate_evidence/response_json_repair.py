"""Narrow repair for unescaped quotes in allowlisted JSON string fields."""

from __future__ import annotations


def _next_non_whitespace(json_text: str, index: int) -> int:
    while index < len(json_text) and json_text[index].isspace():
        index += 1
    return index


def _previous_non_whitespace(json_text: str, index: int) -> int:
    while index >= 0 and json_text[index].isspace():
        index -= 1
    return index


def _find_string_end(json_text: str, opening_quote_index: int) -> int | None:
    index = opening_quote_index + 1
    while index < len(json_text):
        character = json_text[index]
        if character == "\\":
            if index + 1 >= len(json_text):
                return None
            index += 2
            continue
        if character == '"':
            return index
        index += 1
    return None


def _find_repairable_value_quotes(
    json_text: str,
    opening_quote_index: int,
) -> tuple[int, tuple[int, ...]] | None:
    internal_quote_indexes: list[int] = []
    index = opening_quote_index + 1

    while index < len(json_text):
        character = json_text[index]
        if character == "\\":
            if index + 1 >= len(json_text):
                return None
            index += 2
            continue
        if character != '"':
            index += 1
            continue

        following_index = _next_non_whitespace(json_text, index + 1)
        if (
            following_index < len(json_text)
            and json_text[following_index] in {",", "}"}
        ):
            if len(internal_quote_indexes) % 2 != 0:
                return None
            if any(
                (
                    next_index := _next_non_whitespace(
                        json_text,
                        internal_quote_index + 1,
                    )
                )
                < len(json_text)
                and json_text[next_index] == ":"
                for internal_quote_index in internal_quote_indexes
            ):
                return None
            return index, tuple(internal_quote_indexes)

        internal_quote_indexes.append(index)
        index += 1

    return None


def repair_unescaped_quotes_in_string_fields(
    json_text: str,
    *,
    allowed_field_names: frozenset[str],
) -> str:
    """Replace safely paired internal quotes in allowlisted string field values."""

    if not allowed_field_names:
        return json_text

    replacement_indexes: list[int] = []
    index = 0
    while index < len(json_text):
        if json_text[index] != '"':
            index += 1
            continue

        key_end_index = _find_string_end(json_text, index)
        if key_end_index is None:
            return json_text

        key_name = json_text[index + 1 : key_end_index]
        previous_index = _previous_non_whitespace(json_text, index - 1)
        following_index = _next_non_whitespace(json_text, key_end_index + 1)
        is_object_key = (
            (previous_index < 0 or json_text[previous_index] in {"{", ","})
            and following_index < len(json_text)
            and json_text[following_index] == ":"
        )
        if not is_object_key or key_name not in allowed_field_names:
            index = key_end_index + 1
            continue

        value_index = _next_non_whitespace(json_text, following_index + 1)
        if value_index >= len(json_text) or json_text[value_index] != '"':
            index = key_end_index + 1
            continue

        repairable_value = _find_repairable_value_quotes(json_text, value_index)
        if repairable_value is None:
            return json_text

        value_end_index, internal_quote_indexes = repairable_value
        replacement_indexes.extend(internal_quote_indexes)
        index = value_end_index + 1

    if not replacement_indexes:
        return json_text

    characters = list(json_text)
    for pair_index in range(0, len(replacement_indexes), 2):
        characters[replacement_indexes[pair_index]] = "“"
        characters[replacement_indexes[pair_index + 1]] = "”"
    return "".join(characters)


__all__ = ["repair_unescaped_quotes_in_string_fields"]

