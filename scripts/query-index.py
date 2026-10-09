#!/usr/bin/env python3
"""Progressively route a user query to the smallest useful Feeling to Jargon knowledge set."""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load(rel: str):
    with (ROOT / rel).open(encoding="utf-8") as f:
        return json.load(f)

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

def score(query: str, keywords: list[str]) -> int:
    q = normalize(query)
    q_tokens = [token for token in chunks(q) if len(token) >= 3 or any("\u4e00" <= char <= "\u9fff" for char in token)]
    points = 0
    for keyword in keywords:
        candidate = normalize(keyword)
        if candidate in q and (len(candidate) >= 3 or any("\u4e00" <= char <= "\u9fff" for char in candidate)):
            points += 3
            continue
        # Chinese requests often contain a shorter phrase inside a descriptive
        # keyword (e.g. “高可用” inside “高可用模式”). Use overlapping bigrams
        # instead of a heavyweight tokenizer.
        if any(
            phrase[i : i + 2] in q
            for phrase in chinese_runs(candidate)
            for i in range(0, len(phrase) - 1)
        ):
            points += 2
            continue
        points += sum(1 for token in q_tokens if token in candidate)
    return points

def main() -> None:
    parser = argparse.ArgumentParser(description="Progressive Feeling to Jargon runtime query")
    parser.add_argument("query", nargs="+", help="user request")
    parser.add_argument("--max-leaves", type=positive_int, default=None)
    parser.add_argument("--max-entries", type=positive_int, default=None)
    args = parser.parse_args()
    query = " ".join(args.query)
    root = load("index/root.json")
    runtime = load("index/runtime.json")
    limits = root["loading_policy"]
    max_leaves = args.max_leaves if args.max_leaves is not None else limits["max_leaf_packages"]
    max_entries = args.max_entries if args.max_entries is not None else limits["max_entries_per_leaf"]

    ranked = []
    for route in runtime["routes"]:
        route_score = score(query, route["keywords"])
        if route_score:
            ranked.append((route_score, route))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["entry_count"], pair[1]["leaf_id"]))

    # Keep routes close to the best match within each selected subdomain. This
    # preserves one strong route per relevant subdomain while preventing a
    # specific request such as "GSAP timeline" from loading every leaf that
    # shares only the provider keyword.
    initial_selected = ranked[:max_leaves]
    selected_subdomains = []
    for _, route in initial_selected:
        key = (route["domain_id"], route["subdomain_id"])
        if key not in selected_subdomains:
            selected_subdomains.append(key)
    selected_subdomains = selected_subdomains[: limits["max_subdomains"]]
    score_margin = limits.get("route_score_margin", 0)
    selected = []
    for subdomain in selected_subdomains:
        subdomain_ranked = [
            pair for pair in ranked
            if (pair[1]["domain_id"], pair[1]["subdomain_id"]) == subdomain
        ]
        if not subdomain_ranked:
            continue
        top_score = subdomain_ranked[0][0]
        selected.extend(
            pair for pair in subdomain_ranked
            if pair[0] >= max(1, top_score - score_margin)
        )
    selected = selected[:max_leaves]

    # Resolve the selected hierarchy before loading leaf content. The runtime
    # router stays small and hot, while these indexes provide the authoritative
    # domain -> subdomain -> intent path for the selected request.
    domain_index_paths = []
    intent_index_paths = []
    selected_intents = {}
    for domain_id, subdomain_id in selected_subdomains:
        domain_path = f"index/domains/{domain_id}.json"
        domain_doc = load(domain_path)
        domain_index_paths.append(domain_path)
        subdomain = next(item for item in domain_doc["subdomains"] if item["subdomain_id"] == subdomain_id)
        intent_doc = load(subdomain["intent_index"])
        intent_index_paths.append(subdomain["intent_index"])
        selected_intents[(domain_id, subdomain_id)] = {
            intent["id"] for intent in intent_doc.get("intents", [])
        }
    intent_rank = {}
    for route_score, route in selected:
        for intent_id in route.get("intent_ids", []):
            key = (route["domain_id"], route["subdomain_id"], intent_id)
            intent_rank[key] = max(route_score, intent_rank.get(key, 0))
    selected_intent_ids = set()
    for domain_id, subdomain_id in selected_subdomains:
        candidates = [
            (score_value, intent_id)
            for (candidate_domain, candidate_subdomain, intent_id), score_value in intent_rank.items()
            if candidate_domain == domain_id and candidate_subdomain == subdomain_id
        ]
        candidates.sort(key=lambda item: (-item[0], item[1]))
        selected_intent_ids.update(
            (domain_id, subdomain_id, intent_id)
            for _, intent_id in candidates[: limits["max_intents"]]
        )
    selected = [
        pair for pair in selected
        if any(
            (pair[1]["domain_id"], pair[1]["subdomain_id"], intent_id) in selected_intent_ids
            for intent_id in set(pair[1].get("intent_ids", []))
            & selected_intents[(pair[1]["domain_id"], pair[1]["subdomain_id"])]
        )
    ]

    loaded = []
    for route_score, route in selected:
        leaf = load(route["path"])
        terms = []
        for item in leaf.get("entries", [])[:max_entries]:
            searchable = " ".join([item.get("name", ""), item.get("plain_language", ""), item.get("when_to_use", ""), *item.get("aliases", [])])
            if score(query, [searchable]) or not ranked:
                terms.append(item)
        if not terms:
            terms = leaf.get("entries", [])[:max_entries]
        loaded.append({
            "leaf_id": route["leaf_id"], "score": route_score, "knowledge_type": route["knowledge_type"],
            "scope": route["scope"], "do_not_generalize": route["do_not_generalize"],
            "path": route["path"], "entries": terms,
        })

    output = {
        "query": query,
        "strategy": "progressive",
        "trace": {
            "levels": ["root", "subdomain", "intent", "leaf", "entry"],
            "root_loaded": "index/root.json",
            "runtime_router_loaded": "index/runtime.json",
            "domain_index_paths": domain_index_paths,
            "intent_index_paths": intent_index_paths,
            "selected_intents": [
                {"domain_id": d, "subdomain_id": s, "intent_id": i}
                for d, s, i in sorted(selected_intent_ids)
            ],
            "selected_subdomains": [{"domain_id": d, "subdomain_id": s} for d, s in selected_subdomains],
            "loaded_leaf_paths": [item["path"] for item in loaded],
            "loaded_leaf_count": len(loaded),
            "entry_limit": max_entries,
        },
        "matches": loaded,
        "network_search": "not_requested",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
