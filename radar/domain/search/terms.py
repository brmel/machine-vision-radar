from __future__ import annotations

import re
import unicodedata

from radar.domain.model.entities import SearchSettings

MARKS = re.compile("[\u0300-\u036f]")
WORD = re.compile("[a-z0-9]+")

def stem(word: str) -> str:
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("sses", "shes", "ches", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word

def words(text: str) -> list[str]:
    return WORD.findall(MARKS.sub("", unicodedata.normalize("NFKD", text.lower())))

def terms(text: str) -> list[str]:
    return [stem(w) for w in words(text)]

def query_terms(query: str, settings: SearchSettings) -> list[str]:
    out: list[str] = []
    for word in words(query):
        term = stem(word)
        if word not in settings.stopwords and term not in out:
            out.append(term)
    return out
