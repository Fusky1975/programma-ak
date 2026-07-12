from __future__ import annotations

import random

from ak_engine.models.local_encounter import LOCAL_ENCOUNTER_TEMPLATE, LocalEncounterEvent
from ak_engine.report.prose import render


def test_local_encounter_event_has_10_declared_members():
    assert len(LocalEncounterEvent) == 10


def test_local_encounter_event_verbatim_rumors_pas_values():
    # HostAK/TP/RUMORS.PAS ~lines 86, 118-121, 140 -- the real declared
    # story-code constants, not made-up ordinals.
    assert LocalEncounterEvent.HEAR_OF_INVASION.value == 3090
    assert LocalEncounterEvent.PASS_NO_FIGHT.value == 3310
    assert LocalEncounterEvent.BEFRIEND.value == 3311
    assert LocalEncounterEvent.LEARN_TRICKS.value == 3312
    assert LocalEncounterEvent.TOO_DENSE_TO_LEARN.value == 3313
    assert LocalEncounterEvent.RECEIVE_DONATION.value == 3314
    assert LocalEncounterEvent.HEAR_OF_FEATURE.value == 3315
    assert LocalEncounterEvent.FRIENDLY_CHAT.value == 3316
    assert LocalEncounterEvent.GREET_AVOID_COMBAT.value == 3317
    assert LocalEncounterEvent.HEAR_OF_PATROL_INTRUSION.value == 3393


def test_local_encounter_template_covers_every_member():
    assert set(LOCAL_ENCOUNTER_TEMPLATE.keys()) == set(LocalEncounterEvent)


def test_local_encounter_template_verbatim_samples():
    assert LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.FRIENDLY_CHAT] == (
        "< and [ talked/Rdrank_wine for a while/Rtime, then {parted and "
        "}went their separate ways."
    )
    assert LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.TOO_DENSE_TO_LEARN] == (
        "< was very impressed/Rinterested, but couldn't {seem to "
        "}get_the_hang_of/Runderstand it."
    )


def test_local_encounter_template_donation_carries_king_and_alignment_markers():
    # ^K (King name+title) and $a (alignment) -- confirmed real control
    # -byte/marker content transcribed from raw SAY.PAS bytes, not guessed.
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.RECEIVE_DONATION]
    assert "^K's" in template
    assert "$a" in template


def test_local_encounter_template_hear_of_feature_carries_king_exclusion_markers():
    # ^B/^E: PROSE.TXT's own "excluded from the General Intelligence
    # Reports of other players" span, already documented as deferred by
    # report/prose.py's own docstring -- confirmed present here, not
    # silently dropped during transcription.
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.HEAR_OF_FEATURE]
    assert "^B" in template
    assert "^E" in template
    assert "^F" in template


def test_local_encounter_template_hear_of_invasion_uses_province_name_2_marker():
    # ^S: Province name #2 -- the invaded province, distinct from @.
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.HEAR_OF_INVASION]
    assert template.endswith("^S.")


def test_local_encounter_template_renders_via_prose_render():
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.PASS_NO_FIGHT]
    values = {"<": "Aldric", "[": "Borin", "[1": "Borin"}
    result = render(template, values, rng=random.Random(2))
    assert result == "Aldric passed near Borin, but Borin had not the mettle for a fight."


def test_local_encounter_template_hear_of_feature_renders_with_scoped_values():
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.HEAR_OF_FEATURE]
    values = {
        "[1": "Borin",
        "@": "Greenfield",
        "&": "Dungeon",
        "^B": "",
        "^F": "0304",
        "^E": "",
        "+": "Ogres",
    }
    result = render(template, values, rng=random.Random(2))
    assert result == "Borin told of a feature in Greenfield: a Dungeon 0304 occupied by Ogres."


def test_local_encounter_template_receive_donation_renders_with_scoped_values():
    template = LOCAL_ENCOUNTER_TEMPLATE[LocalEncounterEvent.RECEIVE_DONATION]
    values = {
        "<": "Aldric",
        ">": "Aldric's",
        "^K": "King Harold the Bold",
        "$a": "Good",
        "[1": "Borin",
    }
    result = render(template, values, rng=random.Random(2))
    assert result == (
        "Aldric explained King Harold the Bold's Good beliefs and Borin, "
        "visibly impressed, gave us 1 gold."
    )
