"""Turns story entries and questions into text in one viewer's language.

The database stores which line was told and who it was about, never the words. The words
come from the content app, in the viewer's language (falling back to the default language).
"""

import re

from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import get_language, gettext

from content import models as content

PLACEHOLDER = re.compile(r"\{(\w+)\}")


class MissingValue(Exception):
    """A story line has a placeholder that the entry has no value for."""


def current_language():
    """The language code to show, one of settings.LANGUAGES."""
    code = (get_language() or settings.LANGUAGE_CODE).split("-")[0]
    return code if code in dict(settings.LANGUAGES) else settings.LANGUAGE_CODE


def display_name(row):
    """A tribute's name, or "Tribute 3" in the viewer's language if nobody typed one."""
    return row.name or f"{gettext('Tribute')} {row.position + 1}"


class Translator:
    """All the content text for one language, loaded once."""

    def __init__(self, language):
        # The default language goes first so that the viewer's language overrides it where translated.
        languages = list(dict.fromkeys([settings.LANGUAGE_CODE, language]))
        self.lines, self.items, self.events, self.questions, self.options = {}, {}, {}, {}, {}
        for code in languages:
            for row in content.StoryLineTranslation.objects.filter(language=code).select_related("line"):
                self.lines[row.line.natural_key()] = row.text
            for row in content.ItemTranslation.objects.filter(language=code).select_related("item"):
                self.items[row.item.key] = row.name
            for row in content.ArenaEventTranslation.objects.filter(language=code).select_related("event"):
                self.events[row.event.key] = row.name
            for row in content.QuestionTranslation.objects.filter(language=code).select_related("question"):
                self.questions[row.question.key] = row.text
            for row in content.QuestionOptionTranslation.objects.filter(language=code).select_related(
                "option__question"
            ):
                self.options[row.option.natural_key()] = row.label

    def story(self, entry, name_of, strict=False):
        """The HTML of a story entry: tribute names in bold."""
        values = {
            "a": entry.a, "b": entry.b, "sponsor": entry.sponsor, "item": entry.item,
            "n": entry.n, "names": entry.names,
        }  # fmt: skip
        return self.fill(self.lines[entry.line], values, name_of, strict)

    def phase(self, round_number, day, night):
        """The title of a round: The Bloodbath, Day 3 or Night 3."""
        group = "phase.bloodbath" if round_number == 1 else "phase.night" if night else "phase.day"
        return self.fill(self.lines[(group, 0)], {"n": day}, lambda tribute_id: "")

    def question_text(self, decision, name_of, strict=False):
        values = {
            "a": decision.a.id if decision.a else None,
            "b": decision.b.id if decision.b else None,
            "sponsor": decision.sponsor.id if decision.sponsor else None,
            "item": decision.item.key if decision.item else None,
        }
        return self.fill(self.questions[decision.question], values, name_of, strict)

    def option_labels(self, decision, name_of):
        if decision.option_tributes:
            return [name_of(tribute.id) for tribute in decision.option_tributes]
        if decision.option_events:
            return [self.events[event.key] for event in decision.option_events]
        return [self.options[(decision.question, i)] for i in range(decision.option_count)]

    def fill(self, template, values, name_of, strict=False):
        """Fills {a}, {b}, {sponsor}, {item}, {n} and {names} in a template. Returns safe HTML."""

        def bold(tribute_id):
            return f"<b>{escape(name_of(tribute_id))}</b>"

        def replace(match):
            key = match.group(1)
            value = values.get(key)
            if value is None or value == ():
                if strict:
                    raise MissingValue(f"no value for {{{key}}} in: {template}")
                return ""
            if key in ("a", "b", "sponsor"):
                return bold(value)
            if key == "names":
                return ", ".join(bold(tribute_id) for tribute_id in value)
            if key == "item":
                return escape(self.items[value])
            return escape(str(value))

        return mark_safe(PLACEHOLDER.sub(replace, escape(template)))
