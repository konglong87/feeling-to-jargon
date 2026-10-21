"""Existing deterministic lexical matching; no semantic-model claim."""
from __future__ import annotations
import re
import unicodedata

def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower().strip()

def chunks(value: str) -> list[str]:
    text = normalize(value)
    # Keep Chinese runs and latin/digit words; substring matching handles short Chinese phrases.
    return re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9][a-z0-9+.#:/-]*", text)

def chinese_runs(value: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]{2,}", normalize(value))

def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("must be a positive integer")
    return parsed

def unique_keywords(keywords: list[str]) -> list[str]:
    result = []
    seen = set()
    for keyword in keywords:
        normalized = normalize(keyword)
        if normalized not in seen:
            seen.add(normalized)
            result.append(keyword)
    return result

def score(query: str, keywords: list[str]) -> int:
    q = normalize(query)
    q_tokens = {
        token
        for token in chunks(q)
        if len(token) >= 3 or any("\u4e00" <= char <= "\u9fff" for char in token)
    }
    points = 0
    matched_bigrams: set[str] = set()
    matched_tokens: set[str] = set()
    for keyword in unique_keywords(keywords):
        candidate = normalize(keyword)
        if candidate in q and (len(candidate) >= 3 or any("\u4e00" <= char <= "\u9fff" for char in candidate)):
            points += 3
            continue
        # Chinese requests often contain a shorter phrase inside a descriptive
        # keyword (e.g. “高可用” inside “高可用模式”). Count each observed
        # bigram once per route so repeated aliases cannot inflate a score.
        for phrase in chinese_runs(candidate):
            if len(phrase) < 3:
                continue
            matched_indices = {
                index
                for index in range(0, len(phrase) - 1)
                if phrase[index : index + 2] in q
            }
            # A single shared pair such as “卡片” is too generic. Require
            # adjacent pairs from the same descriptive phrase, so the query
            # contains a continuous 3-character fragment rather than two
            # unrelated pairs scattered across the sentence.
            adjacent_indices = {
                index
                for index in matched_indices
                if index + 1 in matched_indices
            }
            if 0 in adjacent_indices:
                matched_bigrams.update(
                    phrase[index : index + 2]
                    for index in adjacent_indices
                )
        matched_tokens.update(token for token in q_tokens if token in candidate)
    return points + (2 * len(matched_bigrams)) + len(matched_tokens)

def select_entries(query: str, entries: list[dict], limit: int, margin: int, default_entry_id=None) -> list[dict]:
    """Rank inside a merged family before applying its entry budget."""
    ranked = []
    normalized_query = normalize(query)
    for position, item in enumerate(entries):
        identifiers = [item.get("id", ""), item.get("name", ""), *item.get("aliases", [])]
        identifiers = [value for value in identifiers if normalize(value)]
        exact = any(len(normalize(value)) >= 3 and normalize(value) in normalized_query for value in identifiers)
        details = [item.get("plain_language", ""), item.get("when_to_use", "")]
        item_score = score(query, identifiers) + score(query, [value for value in details if value])
        if exact or item_score:
            ranked.append((exact, item_score, position, item))
    if not ranked:
        # Families may name an overview; preserve other leaves' legacy fallback.
        if default_entry_id:
            return [item for item in entries if item["id"] == default_entry_id][:limit]
        return entries[:limit]
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
    if ranked[0][0]:
        selected = [item for item in ranked if item[0]]
    else:
        selected = [item for item in ranked if item[1] >= ranked[0][1] - margin]
    return [item[3] for item in selected[:limit]]
