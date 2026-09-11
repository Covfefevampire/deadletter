"""Dead Letter — a literary dictionary bot for Discord.

The bot intentionally keeps configuration in environment variables. In
particular, DISCORD_TOKEN is read at runtime and never belongs in source.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks


LOG = logging.getLogger("dead_letter")
WIKTIONARY_API_URL = "https://en.wiktionary.org/w/api.php"
DATAMUSE_API_URL = "https://api.datamuse.com/words"
DICTIONARY_HEADERS = {
    "User-Agent": "DeadLetterBot/1.0 (Discord dictionary bot; contact via Discord)",
    "Accept": "application/json",
}
STATE_PATH = Path(os.getenv("DEAD_LETTER_STATE_PATH", "dead_letter_state.json"))
WORD_OF_DAY_CHANNEL_ID = os.getenv("WORD_OF_DAY_CHANNEL_ID", "1547049637565964328").strip()
WORD_OF_DAY_TIMEZONE = ZoneInfo("America/Detroit")
WORD_OF_DAY_POST_TIME = time(hour=9, minute=0, tzinfo=WORD_OF_DAY_TIMEZONE)


@dataclass(frozen=True)
class WordOfDay:
    word: str
    note: str
    example: str


@dataclass(frozen=True)
class WritingWord:
    word: str
    part_of_speech: str
    definition: str
    example: str


WORD_OF_THE_DAY = (
    WordOfDay("apricity", "the warmth of the sun in winter", "We lingered in the apricity beside the stone wall."),
    WordOfDay("susurrus", "a soft whispering or rustling sound", "The susurrus of the reeds followed us downriver."),
    WordOfDay("petrichor", "the earthy scent after rain", "Petrichor rose from the garden after the storm."),
    WordOfDay("vellichor", "the strange wistfulness of used bookstores", "Vellichor kept him browsing long after the shop had emptied."),
    WordOfDay("psithurism", "the sound of wind moving through leaves", "At dusk, psithurism filled the old orchard."),
    WordOfDay("cynosure", "a person or thing that attracts attention", "The tiny theatre became the cynosure of the summer festival."),
    WordOfDay("susurration", "a whispering, murmuring, or rustling sound", "A susurration moved through the audience before the curtain rose."),
    WordOfDay("callipygian", "having shapely or beautiful buttocks", "The sculptor studied the callipygian proportions of the marble figure."),
    WordOfDay("ineffable", "too great or beautiful to be expressed in words", "For a moment, the view from the ridge was ineffable."),
    WordOfDay("limerence", "an intense, involuntary infatuation", "His limerence made every ordinary message feel momentous."),
    WordOfDay("mellifluous", "pleasantly smooth and musical to hear", "Her mellifluous reading quieted the restless room."),
    WordOfDay("obambulate", "to walk about or wander", "They obambulated through the museum until closing time."),
    WordOfDay("querencia", "a place where one feels secure or at home", "The porch became her querencia during the long winter."),
    WordOfDay("raconteur", "a person skilled at telling amusing stories", "The old sailor was a raconteur with a tale for every harbor."),
    WordOfDay("eudaemonia", "a state of flourishing or well-being", "The philosopher treated eudaemonia as a daily practice, not a prize."),
)

WRITING_WORDS = (
    WritingWord("liminal", "Adjective", "existing at a threshold or in-between state", "The empty station felt liminal after the last train had gone."),
    WritingWord("wistful", "Adjective", "gently sad because of longing or remembrance", "She gave the old house one wistful glance before turning away."),
    WritingWord("gossamer", "Noun", "something extremely light, delicate, or insubstantial", "A gossamer curtain lifted in the evening breeze."),
    WritingWord("clandestine", "Adjective", "kept secret or concealed", "They held a clandestine meeting beneath the theater balcony."),
    WritingWord("serendipity", "Noun", "a fortunate discovery made by chance", "Finding the lost letter in the old atlas was pure serendipity."),
    WritingWord("quixotic", "Adjective", "idealistic and impractical in a charming or reckless way", "Her quixotic plan was to sail around the world with no map."),
    WritingWord("mercurial", "Adjective", "changing in mood or temperament quickly and unpredictably", "His mercurial mood kept the whole room guessing."),
    WritingWord("mellifluous", "Adjective", "pleasantly smooth and musical to hear", "Her mellifluous voice made even the warning sound gentle."),
    WritingWord("labyrinthine", "Adjective", "complicated and full of confusing twists and turns", "The old quarter was a labyrinthine maze of alleys."),
    WritingWord("effervescent", "Adjective", "lively, enthusiastic, and bubbling with energy", "His effervescent laugh carried across the crowded garden."),
    WritingWord("halcyon", "Adjective", "peaceful, happy, and undisturbed", "They often spoke of the halcyon summers at the lake."),
    WritingWord("tenebrous", "Adjective", "dark, shadowy, or obscure", "A tenebrous forest rose beyond the ruined road."),
    WritingWord("evanescent", "Adjective", "soon disappearing or fading away", "The evanescent glow vanished as the sun slipped below the hills."),
    WritingWord("petrichor", "Noun", "the earthy scent that follows rain", "Petrichor rose from the garden after the storm."),
    WritingWord("rhapsodic", "Adjective", "expressing intense enthusiasm or delight", "He grew rhapsodic when describing the little coastal town."),
    WritingWord("uncanny", "Adjective", "strangely unsettling or difficult to explain", "An uncanny silence settled over the house."),
    WritingWord("saunter", "Verb", "to walk in a relaxed, unhurried way", "He began to saunter down the pier as if he had nowhere else to be."),
    WritingWord("languor", "Noun", "a relaxed, dreamy, or pleasantly tired feeling", "Summer languor kept them talking long after midnight."),
    WritingWord("incandescent", "Adjective", "glowing brightly or showing intense emotion", "Her incandescent anger lit every word of the argument."),
    WritingWord("beguiling", "Adjective", "charming or attractive in a way that may mislead", "The stranger offered a beguiling smile and an impossible story."),
    WritingWord("taciturn", "Adjective", "reserved or saying very little", "The taciturn mechanic knew exactly where the sound was coming from."),
    WritingWord("resplendent", "Adjective", "splendid or dazzling in appearance", "The ballroom looked resplendent beneath the restored chandeliers."),
    WritingWord("brooding", "Adjective", "thoughtful, troubled, or quietly threatening", "A brooding sky gathered over the fields."),
    WritingWord("vivacious", "Adjective", "lively, spirited, and full of energy", "Her vivacious stories kept the passengers awake."),
    WritingWord("rambunctious", "Adjective", "noisy, energetic, and difficult to control", "The rambunctious puppies overturned the basket of yarn."),
    WritingWord("solace", "Noun", "comfort or consolation during sadness or trouble", "He found unexpected solace in the sound of rain."),
    WritingWord("yearning", "Noun", "a strong, persistent longing for someone or something", "A quiet yearning for home followed her through the city."),
    WritingWord("capricious", "Adjective", "given to sudden, unpredictable changes", "The capricious wind scattered their carefully arranged papers."),
    WritingWord("poignant", "Adjective", "deeply moving, especially through sadness or tenderness", "Their poignant farewell lasted only a few seconds."),
    WritingWord("verdant", "Adjective", "green with grass, plants, or other vegetation", "The path opened onto a verdant valley below."),
    WritingWord("portentous", "Adjective", "suggesting that something important or ominous is about to happen", "A portentous hush fell over the crowd."),
    WritingWord("convivial", "Adjective", "friendly, lively, and fond of good company", "The cramped kitchen became the most convivial room in the house."),
    WritingWord("nomadic", "Adjective", "moving from place to place rather than living in one location", "Her nomadic childhood made every new town feel briefly familiar."),
    WritingWord("kinetic", "Adjective", "full of movement, energy, or action", "The dance had a kinetic force that pulled everyone closer."),
    WritingWord("sonorous", "Adjective", "having a deep, rich, or resonant sound", "His sonorous reading filled the old library."),
    WritingWord("mutable", "Adjective", "liable to change or be changed", "Their mutable alliance shifted with every new rumor."),
    WritingWord("audacious", "Adjective", "willing to take bold or surprising risks", "It was an audacious escape, but the timing was perfect."),
    WritingWord("elusive", "Adjective", "difficult to find, catch, understand, or achieve", "The elusive answer appeared only after she stopped looking for it."),
)
RANDOM_WORD_RECENT_LIMIT = 8

CURATED_WORD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "apricity": ("sunshine", "warmth"),
    "susurrus": ("whisper", "murmur", "rustle"),
    "petrichor": ("earthiness", "rain scent"),
    "vellichor": ("nostalgia", "wistfulness"),
    "psithurism": ("rustling", "leaf-whisper"),
    "cynosure": ("center of attention", "focus"),
    "susurration": ("murmur", "whisper", "rustle"),
    "callipygian": ("shapely", "well-proportioned"),
    "ineffable": ("inexpressible", "indescribable"),
    "limerence": ("infatuation", "obsession"),
    "mellifluous": ("musical", "sweet-sounding"),
    "obambulate": ("wander", "roam"),
    "querencia": ("refuge", "sanctuary"),
    "raconteur": ("storyteller", "narrator"),
    "eudaemonia": ("flourishing", "well-being"),
}

# These are deliberately labeled as contextual opposites rather than direct
# antonyms. They are used only when the dictionary sources provide no exact
# antonym, and each group is tied to a distinct sense of the word.
CONTEXTUAL_ANTONYM_GROUPS: dict[str, tuple[dict[str, Any], ...]] = {
    "seek": (
        {"label": "Look for / search for", "words": ("overlook", "ignore")},
        {"label": "Pursue / chase", "words": ("avoid", "evade")},
        {"label": "Try to obtain / ask for", "words": ("refuse", "forgo")},
    ),
}


class DictionaryLookupError(RuntimeError):
    """Raised when the dictionary service cannot provide a usable result."""


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _fallback_example(word: str) -> str:
    return f"The writer chose “{word}” when an ordinary word would not do."


def _define_usage_example(data: dict[str, Any]) -> str:
    """Return a short, original sentence for the /define result.

    Source examples are deliberately not used here: dictionary entries often
    expose quotations, which are not useful as a concise Discord example.
    """
    word = _clean_text(data.get("word")) or "the word"
    curated = next(
        (entry.example for entry in WORD_OF_THE_DAY if entry.word.lower() == word.lower()),
        None,
    )
    if curated:
        return curated

    definitions = data.get("definitions") or []
    meaning = _clean_text(definitions[0]).rstrip(".;:")
    if meaning:
        return f"The writer used {word} to describe {meaning}."
    return _fallback_example(word)


def _strip_wikicode(value: Any) -> str:
    """Turn the small amount of wiki markup used in entries into readable text."""
    text = str(value or "")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^]]+)\]\]", r"\1", text)

    def replace_template(match: re.Match[str]) -> str:
        parts = [part.strip() for part in match.group(1).split("|")]
        name = parts.pop(0).lower()
        positional = [part for part in parts if part and "=" not in part]
        if name in {"l", "m", "mention", "term", "ill", "w"}:
            return positional[-1] if positional else ""
        if name in {"suffix", "prefix", "compound", "affix"}:
            return " + ".join(positional[1:] if len(positional) > 1 else positional)
        if name in {"coin", "coiner", "back-formation"}:
            return "coined"
        if name in {"quote", "quote-book", "quote-journal", "quote-web"}:
            passage = next((part[8:] for part in parts if part.startswith("passage=")), "")
            return passage
        return ""

    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{([^{}]+)\}\}", replace_template, text)
    return _clean_text(text).strip(" .;:")


def _section_body(text: str, heading: str, level: int = 3) -> str:
    """Extract a MediaWiki heading's body until the next heading at that level."""
    marker = "=" * level
    match = re.search(
        rf"^{re.escape(marker)}{re.escape(heading)}{re.escape(marker)}\s*$([\s\S]*?)(?=^"
        rf"{re.escape(marker)}[^=].*?{re.escape(marker)}\s*$|^==[^=].*?==\s*$|\Z)",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    return match.group(1) if match else ""


def _english_section(wikitext: str) -> str:
    match = re.search(r"^==English==\s*$([\s\S]*?)(?=^==[^=].*?==\s*$|\Z)", wikitext, re.IGNORECASE | re.MULTILINE)
    return match.group(1) if match else wikitext


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            result.append(cleaned)
            seen.add(key)
    return result


def _parse_wiktionary(payload: dict[str, Any], word: str) -> dict[str, Any]:
    wikitext = payload.get("parse", {}).get("wikitext", "")
    if isinstance(wikitext, dict):
        wikitext = wikitext.get("*", "")
    if not isinstance(wikitext, str) or not wikitext.strip():
        raise DictionaryLookupError("Wiktionary returned no entry text.")

    english = _english_section(wikitext)
    definitions: list[str] = []
    parts: list[str] = []
    examples: list[str] = []
    synonyms: list[str] = []
    synonym_groups: list[dict[str, Any]] = []
    antonym_groups: list[dict[str, Any]] = []
    known_parts = {
        "noun",
        "proper noun",
        "verb",
        "adjective",
        "adverb",
        "pronoun",
        "preposition",
        "conjunction",
        "interjection",
        "determiner",
        "numeral",
    }
    headings = list(re.finditer(r"^===([^=]+)===\s*$", english, re.MULTILINE))
    for index, heading_match in enumerate(headings):
        heading = _clean_text(heading_match.group(1))
        heading_key = heading.lower()
        if heading_key not in known_parts:
            continue
        body_start = heading_match.end()
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(english)
        body = english[body_start:body_end]
        parts.append(heading)
        for definition_match in re.finditer(r"^#\s+(?![#*:])(.+)$", body, re.MULTILINE):
            definition = _strip_wikicode(definition_match.group(1))
            if definition:
                definitions.append(definition)
        for example_match in re.finditer(r"\|passage=([^}|]+)", body):
            example = _strip_wikicode(example_match.group(1))
            if example:
                examples.append(example)
        for related_heading in ("Synonyms", "Hypernyms", "Coordinate terms"):
            related_body = _section_body(body, related_heading, level=4)
            for template in re.findall(r"\{\{(?:col|syn|synonyms?)\|([^{}]+)\}\}", related_body, re.IGNORECASE):
                for item in template.split("|")[1:]:
                    if "=" not in item:
                        synonyms.extend(item.split(","))
        exact_synonyms: list[str] = []
        related_body = _section_body(body, "Synonyms", level=4)
        for template in re.findall(r"\{\{(?:col|syn|synonyms?)\|([^{}]+)\}\}", related_body, re.IGNORECASE):
            for item in template.split("|")[1:]:
                if "=" not in item:
                    exact_synonyms.extend(item.split(","))
        exact_synonyms = _unique(exact_synonyms)
        if exact_synonyms:
            synonym_groups.append({"label": heading, "words": exact_synonyms})
        exact_antonyms: list[str] = []
        related_body = _section_body(body, "Antonyms", level=4)
        for template in re.findall(r"\{\{(?:col|ant|antonyms?)\|([^{}]+)\}\}", related_body, re.IGNORECASE):
            for item in template.split("|")[1:]:
                if "=" not in item:
                    exact_antonyms.extend(item.split(","))
        exact_antonyms = _unique(exact_antonyms)
        if exact_antonyms:
            antonym_groups.append({"label": heading, "words": exact_antonyms})

    pronunciation_body = _section_body(english, "Pronunciation")
    pronunciation_matches = re.findall(
        r"\{\{IP[A-Za-z]*\|(?:[^|{}]*\|)?([^|{}]+)",
        pronunciation_body,
        re.IGNORECASE,
    )
    pronunciation = _clean_text(pronunciation_matches[0]) if pronunciation_matches else "Not available"

    etymology = _strip_wikicode(_section_body(english, "Etymology")) or "Not available"
    definitions = _unique(definitions)
    if not definitions:
        raise DictionaryLookupError(f"Wiktionary has no English definition for “{word}”.")

    return {
        "word": word,
        "pronunciation": pronunciation,
        "part_of_speech": ", ".join(_unique(parts)) or "Not available",
        "definitions": definitions,
        "synonyms": _unique(synonyms),
        "synonym_groups": synonym_groups,
        "antonym_groups": antonym_groups,
        "etymology": etymology,
        "example": _unique(examples)[0] if examples else None,
        "source_name": "Wiktionary",
        "source_url": f"https://en.wiktionary.org/wiki/{quote(word)}",
    }


def _parse_datamuse(payload: list[dict[str, Any]], word: str, synonyms: list[str]) -> dict[str, Any]:
    if not payload:
        raise DictionaryLookupError(f"Datamuse has no definition for “{word}”.")
    entry = next((item for item in payload if item.get("word", "").lower() == word), payload[0])
    definitions: list[str] = []
    parts: list[str] = []
    for raw_definition in entry.get("defs", []) or []:
        text = str(raw_definition or "").strip()
        prefix, separator, definition = text.partition("\t")
        if separator:
            if prefix:
                parts.append(prefix)
            text = definition
        text = _clean_text(text)
        text = re.sub(r"^\([^)]*\)\s*", "", text)
        if text:
            definitions.append(text)
    if not definitions:
        raise DictionaryLookupError(f"Datamuse has no readable definition for “{word}”.")
    return {
        "word": _clean_text(entry.get("word")) or word,
        "pronunciation": next(
            (_clean_text(str(tag)[5:]) for tag in entry.get("tags", []) if str(tag).startswith("pron:")),
            "Not available",
        ),
        "part_of_speech": ", ".join(_unique(parts)) or "Not available",
        "definitions": _unique(definitions),
        "synonyms": _unique(synonyms),
        "synonym_groups": (
            [{"label": ", ".join(_unique(parts)) or "Related words", "words": _unique(synonyms)}]
            if synonyms
            else []
        ),
        "etymology": "Not available",
        "example": None,
        "source_name": "Datamuse",
        "source_url": f"https://api.datamuse.com/words?sp={quote(word)}&md=dpsr",
    }


async def _request_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, str],
) -> Any:
    async with session.get(url, params=params) as response:
        if response.status != 200:
            raise DictionaryLookupError(f"Dictionary source returned HTTP {response.status}.")
        return await response.json(content_type=None)


async def lookup_word(word: str) -> dict[str, Any]:
    normalized = word.strip().lower()
    if not normalized or len(normalized) > 80:
        raise DictionaryLookupError("Please provide one word, up to 80 characters long.")
    if any(character.isspace() for character in normalized):
        raise DictionaryLookupError("Please provide one word at a time.")

    timeout = aiohttp.ClientTimeout(total=6, connect=3, sock_read=5)
    errors: list[str] = []
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=DICTIONARY_HEADERS) as session:
            try:
                wiktionary_payload = await _request_json(
                    session,
                    WIKTIONARY_API_URL,
                    params={
                        "action": "parse",
                        "page": normalized,
                        "prop": "wikitext",
                        "format": "json",
                        "formatversion": "2",
                    },
                )
                return _parse_wiktionary(wiktionary_payload, normalized)
            except (DictionaryLookupError, asyncio.TimeoutError, aiohttp.ClientError, ValueError) as error:
                errors.append(f"Wiktionary: {error}")
                LOG.warning("Primary dictionary lookup failed for %s: %s", normalized, error)

            try:
                datamuse_payload = await _request_json(
                    session,
                    DATAMUSE_API_URL,
                    params={"sp": normalized, "md": "dpsr", "max": "1"},
                )
                synonyms_payload = await _request_json(
                    session,
                    DATAMUSE_API_URL,
                    params={"rel_syn": normalized, "max": "12"},
                )
                synonym_words = [
                    item.get("word", "")
                    for item in synonyms_payload
                    if isinstance(item, dict) and item.get("word")
                ]
                return _parse_datamuse(datamuse_payload, normalized, synonym_words)
            except (DictionaryLookupError, asyncio.TimeoutError, aiohttp.ClientError, ValueError) as error:
                errors.append(f"Datamuse: {error}")
                LOG.warning("Fallback dictionary lookup failed for %s: %s", normalized, error)
    except (asyncio.TimeoutError, aiohttp.ClientError) as error:
        errors.append(f"Network: {error}")

    LOG.error("All dictionary sources failed for %s: %s", normalized, "; ".join(errors))
    raise DictionaryLookupError(f"I couldn't find a definition for “{normalized}” right now.")


async def lookup_synonyms(data: dict[str, Any]) -> dict[str, Any]:
    """Add direct Datamuse synonyms only for the dedicated synonym command."""
    if data.get("synonym_groups"):
        return data

    word = _clean_text(data.get("word")).lower()
    if not word:
        return data

    timeout = aiohttp.ClientTimeout(total=4, connect=2, sock_read=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=DICTIONARY_HEADERS) as session:
            payload = await _request_json(
                session,
                DATAMUSE_API_URL,
                params={"rel_syn": word, "max": "12"},
            )
    except (asyncio.TimeoutError, aiohttp.ClientError, DictionaryLookupError, ValueError) as error:
        LOG.warning("Direct synonym enrichment failed for %s: %s", word, error)
        return data

    synonyms = _unique([
        item.get("word", "")
        for item in payload
        if isinstance(item, dict) and item.get("word", "").lower() != word
    ])
    if not synonyms:
        return data

    enriched = dict(data)
    enriched["synonym_groups"] = [
        {
            "label": data.get("part_of_speech") or "Direct synonyms",
            "words": synonyms,
        }
    ]
    enriched["synonym_source_name"] = "Datamuse"
    return enriched


async def lookup_antonyms(data: dict[str, Any]) -> dict[str, Any]:
    """Add direct Datamuse antonyms only for the dedicated antonym command."""
    if data.get("antonym_groups"):
        return data

    word = _clean_text(data.get("word")).lower()
    if not word:
        return data

    timeout = aiohttp.ClientTimeout(total=4, connect=2, sock_read=3)
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=DICTIONARY_HEADERS) as session:
            payload = await _request_json(
                session,
                DATAMUSE_API_URL,
                params={"rel_ant": word, "max": "12"},
            )
    except (asyncio.TimeoutError, aiohttp.ClientError, DictionaryLookupError, ValueError) as error:
        LOG.warning("Direct antonym enrichment failed for %s: %s", word, error)
        payload = []

    antonyms = _unique([
        item.get("word", "")
        for item in payload
        if isinstance(item, dict) and item.get("word", "").lower() != word
    ])
    enriched = dict(data)
    if antonyms:
        enriched["antonym_groups"] = [
            {
                "label": data.get("part_of_speech") or "Direct antonyms",
                "words": antonyms,
            }
        ]
        enriched["antonym_source_name"] = "Datamuse"
        return enriched

    contextual_groups = CONTEXTUAL_ANTONYM_GROUPS.get(word)
    if contextual_groups:
        enriched["contextual_antonym_groups"] = [
            {"label": group["label"], "words": list(group["words"])}
            for group in contextual_groups
        ]
        enriched["contextual_antonym_source_name"] = "Dead Letter sense guide"
    return enriched


def make_definition_embed(data: dict[str, Any]) -> discord.Embed:
    definitions = data["definitions"][:3]
    definition_text = "\n".join(f"{index}. {item}" for index, item in enumerate(definitions, 1))
    if len(definition_text) > 1024:
        definition_text = f"{definition_text[:1000].rsplit(' ', 1)[0]}…"

    synonyms = ", ".join(data["synonyms"][:12]) or "Not available"
    if len(synonyms) > 1024:
        synonyms = f"{synonyms[:1000].rsplit(' ', 1)[0]}…"

    embed = discord.Embed(
        title=f"Dead Letter · {data['word']}",
        description=definition_text or "No definition was provided.",
        color=discord.Color.from_rgb(83, 61, 104),
        url=data.get("source_url"),
    )
    embed.add_field(name="Part of speech", value=data["part_of_speech"], inline=True)
    embed.add_field(name="Pronunciation", value=data["pronunciation"], inline=True)
    embed.add_field(name="Synonyms", value=synonyms, inline=False)
    embed.add_field(name="Etymology", value=data["etymology"], inline=False)
    embed.add_field(name="Example", value=_define_usage_example(data), inline=False)
    embed.set_footer(text=f"Source: {data.get('source_name', 'dictionary')}")
    return embed


def make_synonym_embed(data: dict[str, Any]) -> discord.Embed:
    part_of_speech = data.get("part_of_speech") or "Not available"
    embed = discord.Embed(
        title=f"Dead Letter · Synonyms for {data['word']}",
        description=f"**Part of speech:** {part_of_speech}",
        color=discord.Color.from_rgb(65, 104, 91),
        url=data.get("source_url"),
    )

    groups = data.get("synonym_groups") or []
    valid_groups = [
        group for group in groups
        if isinstance(group, dict) and group.get("words")
    ]
    if not valid_groups:
        embed.add_field(
            name="No useful synonyms found",
            value="This word does not have reliable direct synonyms in the available sources.",
            inline=False,
        )
    else:
        for group in valid_groups[:10]:
            words = _unique([str(word) for word in group["words"]])[:16]
            if words:
                label = _clean_text(group.get("label")) or "Related meaning"
                embed.add_field(name=label, value=", ".join(words), inline=False)

    source = data.get("source_name", "dictionary")
    synonym_source = data.get("synonym_source_name")
    footer = f"Source: {source}"
    if synonym_source and synonym_source != source:
        footer = f"Definition: {source} · Synonyms: {synonym_source}"
    embed.set_footer(text=footer)
    return embed


def make_antonym_embed(data: dict[str, Any]) -> discord.Embed:
    part_of_speech = data.get("part_of_speech") or "Not available"
    contextual_groups = data.get("contextual_antonym_groups") or []
    has_contextual_groups = any(
        isinstance(group, dict) and group.get("words")
        for group in contextual_groups
    )
    description = f"**Part of speech:** {part_of_speech}"
    if has_contextual_groups:
        description += (
            "\n\n**No single exact dictionary antonym was found.** "
            "These are contextual opposites for different senses, not direct antonyms."
        )
    embed = discord.Embed(
        title=f"Dead Letter · Antonyms for {data['word']}",
        description=description,
        color=discord.Color.from_rgb(126, 75, 86),
        url=data.get("source_url"),
    )

    groups = data.get("antonym_groups") or []
    valid_groups = [
        group for group in groups
        if isinstance(group, dict) and group.get("words")
    ]
    if valid_groups:
        for group in valid_groups[:10]:
            words = _unique([str(word) for word in group["words"]])[:16]
            if words:
                label = _clean_text(group.get("label")) or "Opposite meaning"
                embed.add_field(name=label, value=", ".join(words), inline=False)
    elif has_contextual_groups:
        for group in contextual_groups[:10]:
            if not isinstance(group, dict):
                continue
            words = _unique([str(word) for word in group.get("words", [])])[:16]
            if words:
                label = _clean_text(group.get("label")) or "Contextual opposite"
                embed.add_field(
                    name=f"Contextual · {label}",
                    value=", ".join(words),
                    inline=False,
                )
    else:
        embed.add_field(
            name="No exact antonym found",
            value="This word does not have a reliable direct antonym in the available sources.",
            inline=False,
        )

    source = data.get("source_name", "dictionary")
    antonym_source = data.get("antonym_source_name")
    contextual_source = data.get("contextual_antonym_source_name")
    footer = f"Source: {source}"
    if antonym_source and antonym_source != source:
        footer = f"Definition: {source} · Antonyms: {antonym_source}"
    elif contextual_source:
        footer = f"Definition: {source} · Contextual opposites: Dead Letter"
    embed.set_footer(text=footer)
    return embed


def make_random_word_embed(word: WritingWord) -> discord.Embed:
    embed = discord.Embed(
        title="Dead Letter · Random Writing Word",
        description=f"**{word.word}**",
        color=discord.Color.from_rgb(111, 79, 45),
    )
    embed.add_field(name="Part of speech", value=word.part_of_speech, inline=True)
    embed.add_field(name="Definition", value=word.definition, inline=False)
    embed.add_field(name="Example", value=word.example, inline=False)
    embed.add_field(
        name="Challenge",
        value="Challenge: work this word naturally into your current scene.",
        inline=False,
    )
    embed.set_footer(text="A curated writing prompt · /randomword for another")
    return embed


def make_word_of_day_embed(word: WordOfDay, data: dict[str, Any] | None) -> discord.Embed:
    if data:
        definition = data["definitions"][0] if data["definitions"] else word.note
        pronunciation = data["pronunciation"]
        part_of_speech = data["part_of_speech"]
        etymology = data["etymology"]
        synonyms = data["synonyms"] or CURATED_WORD_SYNONYMS.get(word.word, ())
    else:
        definition = word.note
        pronunciation = "Not available"
        part_of_speech = "Not available"
        etymology = "Not available"
        synonyms = CURATED_WORD_SYNONYMS.get(word.word, ())

    embed = discord.Embed(
        title=f"Word of the Day · {word.word}",
        description=definition,
        color=discord.Color.from_rgb(154, 102, 60),
    )
    embed.add_field(name="Part of speech", value=part_of_speech, inline=True)
    embed.add_field(name="Pronunciation", value=pronunciation, inline=True)
    embed.add_field(name="Synonyms", value=", ".join(synonyms) or "Not available", inline=False)
    embed.add_field(name="Etymology", value=etymology, inline=False)
    embed.add_field(name="Example", value=word.example, inline=False)
    embed.set_footer(text="A small word for a large vocabulary · /define to investigate another")
    return embed


class DeadLetter(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.state: dict[str, Any] = self._load_state()
        self.http_session: aiohttp.ClientSession | None = None
        self._guild_commands_synced = False
        self._word_of_day_post_lock = asyncio.Lock()

    @staticmethod
    def _load_state() -> dict[str, Any]:
        try:
            content = STATE_PATH.read_text(encoding="utf-8")
            loaded = json.loads(content)
            return loaded if isinstance(loaded, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_state(self) -> None:
        try:
            STATE_PATH.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            LOG.exception("Could not save Word of the Day state.")

    def choose_random_writing_word(self, scope: str) -> WritingWord:
        all_histories = self.state.get("_random_word_history", {})
        histories = all_histories if isinstance(all_histories, dict) else {}
        recent = histories.get(scope, [])
        recent = [str(word) for word in recent if word] if isinstance(recent, list) else []

        available = [word for word in WRITING_WORDS if word.word not in recent]
        if not available:
            recent = []
            available = list(WRITING_WORDS)

        selected = random.choice(available)
        histories[scope] = (recent + [selected.word])[-RANDOM_WORD_RECENT_LIMIT:]
        self.state["_random_word_history"] = histories
        self._save_state()
        return selected

    def _get_word_state(self, guild_id: int) -> dict[str, Any]:
        raw_state = self.state.get(str(guild_id))
        if isinstance(raw_state, str):
            # Migrate the original date-only state format without losing the
            # restart protection it already provided.
            return {
                "last_posted_date": raw_state,
                "last_word": "",
                "used_words": [],
            }
        if not isinstance(raw_state, dict):
            return {
                "last_posted_date": "",
                "last_word": "",
                "used_words": [],
            }
        used_words = raw_state.get("used_words", [])
        return {
            "last_posted_date": str(raw_state.get("last_posted_date", "")),
            "last_word": str(raw_state.get("last_word", "")),
            "used_words": [str(word) for word in used_words if word],
        } if isinstance(used_words, list) else {
            "last_posted_date": str(raw_state.get("last_posted_date", "")),
            "last_word": str(raw_state.get("last_word", "")),
            "used_words": [],
        }

    @staticmethod
    def _choose_word(word_state: dict[str, Any]) -> WordOfDay:
        used_words = set(word_state.get("used_words", []))
        available = [word for word in WORD_OF_THE_DAY if word.word not in used_words]
        if not available:
            # The curated list is finite; only begin a new cycle after every
            # word has been used once.
            word_state["used_words"] = []
            available = list(WORD_OF_THE_DAY)
        return random.choice(available)

    async def _find_word_of_day_post_today(
        self,
        channel: discord.TextChannel,
    ) -> tuple[bool, str] | None:
        """Return whether this bot posted a Word of the Day in the channel today.

        None means Discord would not let us verify history, so callers should
        fail closed rather than risk creating a duplicate.
        """
        me = self.user
        permissions = channel.permissions_for(channel.guild.me) if channel.guild.me else None
        if me is None or permissions is None or not permissions.read_message_history:
            LOG.warning("Cannot verify Word of the Day history in #%s.", channel.name)
            return None

        local_today = datetime.now(WORD_OF_DAY_TIMEZONE).date()
        start_of_day = datetime.combine(
            local_today,
            time.min,
            tzinfo=WORD_OF_DAY_TIMEZONE,
        ).astimezone(timezone.utc)
        try:
            async for message in channel.history(
                limit=None,
                after=start_of_day,
                oldest_first=False,
            ):
                if message.author.id != me.id:
                    continue
                for embed in message.embeds:
                    title = embed.title or ""
                    prefix = "Word of the Day · "
                    if title.startswith(prefix):
                        return True, title[len(prefix):].strip()
        except (discord.Forbidden, discord.HTTPException):
            LOG.exception("Could not inspect Word of the Day history in #%s.", channel.name)
            return None
        return False, ""

    def _record_word_of_day_post(
        self,
        guild_id: int,
        today: str,
        word: str,
    ) -> None:
        word_state = self._get_word_state(guild_id)
        used_words = set(word_state.get("used_words", []))
        if word:
            used_words.add(word)
        self.state[str(guild_id)] = {
            "last_posted_date": today,
            "last_word": word or word_state.get("last_word", ""),
            "used_words": sorted(used_words),
        }
        self._save_state()

    async def setup_hook(self) -> None:
        self.tree.add_command(define_command)
        self.tree.add_command(wordoftheday_command)
        self.tree.add_command(synonym_command)
        self.tree.add_command(antonym_command)
        self.tree.add_command(randomword_command)
        self.tree.add_command(grammar_command)
        synced = await self.tree.sync()
        LOG.info(
            "Global application commands synced: %s",
            ", ".join(command.name for command in synced) or "none",
        )
        self.daily_word.start()

    async def on_ready(self) -> None:
        LOG.info("Logged in as %s (ID %s)", self.user, self.user.id if self.user else "unknown")
        LOG.info("Connected to %d guild(s).", len(self.guilds))
        if not self._guild_commands_synced:
            for guild in self.guilds:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                LOG.info(
                    "Guild application commands synced for %s (%s): %s",
                    guild.name,
                    guild.id,
                    ", ".join(command.name for command in synced) or "none",
                )
            self._guild_commands_synced = True

        for guild in self.guilds:
            await self.post_word_of_day(guild)

    async def close(self) -> None:
        if self.daily_word.is_running():
            self.daily_word.cancel()
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def post_word_of_day(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ) -> tuple[discord.TextChannel, WordOfDay] | None:
        async with self._word_of_day_post_lock:
            return await self._post_word_of_day(guild, force=force)

    async def _post_word_of_day(
        self,
        guild: discord.Guild,
        *,
        force: bool = False,
    ) -> tuple[discord.TextChannel, WordOfDay] | None:
        today = datetime.now(WORD_OF_DAY_TIMEZONE).date().isoformat()
        word_state = self._get_word_state(guild.id)

        channel = await self.find_word_channel(guild)
        if channel is None:
            LOG.warning(
                "Configured Word of the Day channel %s is unavailable or not writable in %s.",
                WORD_OF_DAY_CHANNEL_ID,
                guild.name,
            )
            return

        if not force:
            history = await self._find_word_of_day_post_today(channel)
            if history is None:
                return None
            already_posted, posted_word = history
            if already_posted:
                known_word = next(
                    (
                        entry.word
                        for entry in WORD_OF_THE_DAY
                        if entry.word.lower() == posted_word.lower()
                    ),
                    "",
                )
                self._record_word_of_day_post(guild.id, today, known_word)
                LOG.info("Word of the Day already posted today in %s.", guild.name)
                return None

        word = next(
            (entry for entry in WORD_OF_THE_DAY if entry.word == word_state["last_word"]),
            None,
        ) if force and word_state["last_posted_date"] == today else None
        word = word or self._choose_word(word_state)
        try:
            data = await lookup_word(word.word)
        except DictionaryLookupError as error:
            LOG.warning("Falling back to curated entry for %s: %s", word.word, error)
            data = None

        try:
            await channel.send(embed=make_word_of_day_embed(word, data))
        except discord.Forbidden:
            LOG.warning("Missing permission to post in #%s in %s.", channel.name, guild.name)
            return
        except discord.HTTPException:
            LOG.exception("Discord rejected the Word of the Day message in %s.", guild.name)
            return

        self._record_word_of_day_post(guild.id, today, word.word)
        LOG.info("Posted Word of the Day %s in %s.", word.word, guild.name)
        return channel, word

    async def find_word_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        me = guild.me
        if me is None or not WORD_OF_DAY_CHANNEL_ID.isdigit():
            return None
        configured = guild.get_channel(int(WORD_OF_DAY_CHANNEL_ID))
        if isinstance(configured, discord.TextChannel) and configured.permissions_for(me).send_messages:
            return configured
        return None

    @tasks.loop(time=WORD_OF_DAY_POST_TIME)
    async def daily_word(self) -> None:
        for guild in self.guilds:
            await self.post_word_of_day(guild)

    @daily_word.before_loop
    async def before_daily_word(self) -> None:
        await self.wait_until_ready()


bot = DeadLetter()


@app_commands.command(name="define", description="Look up a word in Dead Letter's dictionary.")
@app_commands.describe(word="The single word you want to investigate.")
async def define_command(interaction: discord.Interaction, word: str) -> None:
    await interaction.response.defer(thinking=True)
    try:
        data = await lookup_word(word)
    except DictionaryLookupError as error:
        await interaction.followup.send(f"**Dead Letter:** {error}", ephemeral=True)
        return
    await interaction.followup.send(embed=make_definition_embed(data))


@app_commands.command(name="synonym", description="Find useful synonyms for a word.")
@app_commands.describe(word="The single word you want synonyms for.")
async def synonym_command(interaction: discord.Interaction, word: str) -> None:
    await interaction.response.defer(thinking=True)
    try:
        data = await lookup_word(word)
        data = await lookup_synonyms(data)
    except DictionaryLookupError as error:
        await interaction.followup.send(f"**Dead Letter:** {error}", ephemeral=True)
        return
    await interaction.followup.send(embed=make_synonym_embed(data))


@app_commands.command(name="antonym", description="Find useful antonyms for a word.")
@app_commands.describe(word="The single word you want antonyms for.")
async def antonym_command(interaction: discord.Interaction, word: str) -> None:
    await interaction.response.defer(thinking=True)
    try:
        data = await lookup_word(word)
        data = await lookup_antonyms(data)
    except DictionaryLookupError as error:
        await interaction.followup.send(f"**Dead Letter:** {error}", ephemeral=True)
        return
    await interaction.followup.send(embed=make_antonym_embed(data))


@app_commands.command(name="randomword", description="Get a random word for your current writing scene.")
async def randomword_command(interaction: discord.Interaction) -> None:
    scope = (
        f"guild:{interaction.guild_id}"
        if interaction.guild_id is not None
        else f"user:{interaction.user.id}"
    )
    word = bot.choose_random_writing_word(scope)
    await interaction.response.send_message(embed=make_random_word_embed(word))

@app_commands.command(
    name="grammar",
    description="Check the grammar of a sentence."
)
@app_commands.describe(sentence="The sentence you want Dead Letter to check.")
async def grammar_command(
    interaction: discord.Interaction,
    sentence: str
) -> None:
    await interaction.response.defer(thinking=True)

    url = "https://api.languagetool.org/v2/check"
    payload = {
        "text": sentence,
        "language": "en-US"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as response:
                data = await response.json()

        matches = data.get("matches", [])

        if not matches:
            await interaction.followup.send(
                f"**Dead Letter:** I found no grammar errors in:\n\n{sentence}"
            )
            return

        corrected = sentence

        for match in reversed(matches):
            replacements = match.get("replacements", [])
            if replacements:
                start = match["offset"]
                end = start + match["length"]
                corrected = (
                    corrected[:start]
                    + replacements[0]["value"]
                    + corrected[end:]
                )

        await interaction.followup.send(
            f"**Original:**\n{sentence}\n\n"
            f"**Suggested:**\n{corrected}"
        )

    except Exception:
        await interaction.followup.send(
            "**Dead Letter:** I couldn't check that sentence right now.",
            ephemeral=True
        )
@app_commands.command(name="wordoftheday", description="Post today's curated Word of the Day.")
async def wordoftheday_command(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used inside a server.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    posted = await bot.post_word_of_day(interaction.guild, force=True)
    if posted is None:
        await interaction.followup.send(
            f"I couldn't post in <#{WORD_OF_DAY_CHANNEL_ID}>. "
            "Check that the channel exists and that I can send messages and embeds there.",
            ephemeral=True,
        )
        return

    channel, word = posted
    await interaction.followup.send(
        f"Posted **{word.word}** in {channel.mention}.",
        ephemeral=True,
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Add the bot token as an environment variable or Replit Secret."
        )
    bot.run(token)


if __name__ == "__main__":
    main()
