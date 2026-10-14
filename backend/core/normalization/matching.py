from __future__ import annotations


def normalize_for_match(text: str | None) -> str:
    """Collapse whitespace and lowercase *text* for comparison."""
    if not text:
        return ""
    return "".join(str(text).strip().split()).lower()


def match_text(
    heading_text: str,
    heading_terms: tuple[str, ...],
    match_mode: str,
) -> tuple[bool, str | None]:
    """
    Test whether *heading_text* matches any of *heading_terms*.

    Parameters
    ----------
    heading_text:
        The raw or stripped heading string to test.
    heading_terms:
        For exact matching, terms are checked in order and the first exact
        match is returned. For contains matching, all matching terms are
        considered and the longest normalized matching term is returned;
        original order is used only as a tie-breaker.
    match_mode:
        ``"exact"`` — full equality after normalization.
        ``"contains"`` — term is a substring of the heading after normalization.

    Returns
    -------
    tuple[bool, str | None]
        ``(True, matched_term)`` on match, ``(False, None)`` otherwise.
    """
    normalized_heading = normalize_for_match(heading_text)

    if match_mode == "exact":
        for term in heading_terms:
            normalized_term = normalize_for_match(term)
            if not normalized_term:
                continue
            if normalized_heading == normalized_term:
                return True, term
        return False, None

    if match_mode == "contains":
        best_term: str | None = None
        best_len = -1

        for term in heading_terms:
            normalized_term = normalize_for_match(term)
            if not normalized_term:
                continue
            if normalized_term in normalized_heading:
                term_len = len(normalized_term)
                if term_len > best_len:
                    best_term = term
                    best_len = term_len

        if best_term is not None:
            return True, best_term
        return False, None

    raise ValueError(f"Unsupported heading match mode: {match_mode}")
