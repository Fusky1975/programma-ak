"""How a character arrives at / discovers a geographic ``Feature`` --
the narrative "intro" scenario shown once, before the encounter itself
plays out.

``HostAK/TP/CTME.PAS``'s own ``intro`` enum (~line 520, 15 members) plus
``HostAK/TP/PROSE/ENCSPEC.X2`` (header ``"15 1"``, 15 templates), found
continuing to mine the ``PROSE/`` ``.X2`` template files the way Phases
96-98 found their own real data.

**Weaker evidence than Phases 96-98, documented honestly rather than
overstated**: every prior ``.X2``-sourced phase confirmed its file via a
literal ``FD(...)``/``Say(...)`` dispatch call site somewhere in the
available Pascal archive. For ``ENCSPEC.X2``, no such call site exists
anywhere in the 13 available library files (checked case-insensitively
for both ``"encspec"`` and any ``intro[``-style array indexing) --
``YAK.PAS``'s own ``Set_Event`` computes and populates the value
(``fintro:= intro(ord(fintro1[ft]) + IRand MOD (ord(fintrof[ft])
-ord(fintro1[ft])+1))``, a real, populated per-``Feature``-instance
random pick from real, populated ``fintro1``/``fintrof`` range tables --
``CONST fintro1/fintrof: ARRAY[feature] OF intro``, ~line 525/534) but
nothing observable ever *reads* ``fintro`` again -- the same "computed
but no confirmed consumer" gap category as ``comfeat``/``fcomfeat``
(``models/power.py``'s own Phase 95 docstring). The missing main program
(this project's own recurring, documented gap) is the most likely
explanation.

What *does* support this module's positional mapping, short of a literal
citation: ``ENCSPEC.X2``'s own declared choice count (15) matches
``intro``'s own 15 members exactly, and every individual template's
content specifically and unambiguously matches its corresponding
Pascal identifier's plain meaning -- e.g. template 6 ("< entered ... then
eased_down ... the stairs ... leading ... down") is ``DownStairs``,
template 7 ("< started ... climb up the ... staircase") is ``UpStairs``,
template 13 ("< swam ... into the &") is ``Swim``. This is stronger than
a coincidental fit (unlike ``MAGFEAT.X2``'s 19 identical filler lines,
every one of these 15 lines is distinct and semantically on-point), but
it remains inferred from internal consistency, not sourced from a
dispatch call -- flagged here, not silently presented as equally solid.

``INTRO_TEMPLATE``'s own strings are raw, unrendered prose templates --
matching how ``models/weapon.py WEAPON_HIT_VERB``/``models/power.py
POWER_DESCRIPTION`` already store their own raw template text rather
than a pre-resolved sentence. ``fintro1``/``fintrof`` (the per-
``FeatureType`` range tables that pick which ``Intro`` values are
possible for a given Feature) are confirmed real but deliberately out of
scope here, matching how ``models/magic_feature.py`` (Phase 92) deferred
its own analogous ``mf1``/``mff`` tables.
"""

from __future__ import annotations

from enum import Enum


class Intro(Enum):
    """``CTME.PAS``'s own ``intro`` enum, verbatim order and identifiers
    (already meaningful English words, unlike ``Discovery``'s
    ``fix``/``wreck``/``bild``/``crunch`` prefixes -- kept as-is rather
    than derived from ``INTRO_TEMPLATE``'s own prose, matching this
    project's ``Monster``/``Race`` precedent for already-readable Pascal
    identifiers).
    """

    NONE = 0
    MONK = 1
    VALET = 2
    CALL = 3
    WALK_INTO = 4
    DOWN_STAIRS = 5
    UP_STAIRS = 6
    CLIMB_UP = 7
    WALK_UP_TO = 8
    WANDER = 9
    WALK_MID = 10
    WADE = 11
    SWIM = 12
    SAIL = 13
    DIVE = 14


# HostAK/TP/PROSE/ENCSPEC.X2, verbatim, positional with `Intro`'s own
# ordinals above. Raw, unrendered prose templates -- see module docstring.
INTRO_TEMPLATE: dict[Intro, str] = {
    Intro.NONE: "None.",
    Intro.MONK: (
        "< rang_the_bell/Rhad_>_squire_announce_<, and/Rwhereupon a "
        "monk/Rpriest {promptly/Rsoon }came_to/Rshowed_up_at the "
        "door/Rgate.He showed/Rguided <2 in to see/Rthe_court_of [."
    ),
    Intro.VALET: (
        "< called_out_at/Rbeat_his_sword_on the entrance/R&'s_portal.A "
        "valet/Rservant showed{ up}{ at the entrance},{ "
        "quaking/Rshivering with fear,} and {hastily/Rsomewhat_reluctantly "
        "}took/Ragreed_to_guide <2 to see/Rmeet [."
    ),
    Intro.CALL: (
        "{At the entrance, }< called_out_to_[/Rhad_>_squire_herald_>_coming."
        "Soon/Rafter_a_long_delay, [1 appeared/Rcame to greet/Rface <2."
    ),
    Intro.WALK_INTO: "< walked/Rstrode {confidently/Rbravely }into the &.",
    Intro.DOWN_STAIRS: (
        "< entered/Rregarded the & with awe/Rtrepidation, then "
        "eased_down/Rnegotiated the stairs/Rstaircase "
        "leading/Rwhich_descended {down }to [."
    ),
    Intro.UP_STAIRS: (
        "< started/Rembarked_upon the tiring/Rlong climb/Rascent up the "
        "{circular/Rwinding }staircase {leading/Rwhich_spiraled_up }to "
        "{the lair/Rabode of }[."
    ),
    Intro.CLIMB_UP: (
        "< girded_<2self_for/Rbegan the long/Rgrueling climb/Rascent, "
        "and after a_long_time/Rnumbingly_strenuous_exertions {which "
        "seemed to last/Rgo_on_for ^A eternity/Rmillenium, }< "
        "finally/Rat_last found_himself_at/Rreached the "
        "resting_place/Reyrie of [."
    ),
    Intro.WALK_UP_TO: "< walked_up_to/Rreached the & and encountered/Rmet [.",
    Intro.WANDER: (
        "< entered/Rpassed_into the & and encountered/Rwas_confounded_by "
        "a {bewildering }myriad/Rplethora of passageways/Rhallways{ and "
        "dead_ends/Rblind_alleys}."
    ),
    Intro.WALK_MID: (
        "< walked_into/Rreached the middle/Rcenter of the & and "
        "encountered/Rconfronted [."
    ),
    Intro.WADE: (
        "< waded/Rsloshed {> way }into the &.soon, [1{'s head} "
        "appeared_at/Rrose_to the surface/Rcresting_waves."
    ),
    Intro.SWIM: (
        "< swam/Rbegan_swimming into the &, determined/Rhaving_resolved "
        "to confront/Rkeep_>_appointment_with the_dangers_of_the_deep/R"
        ">_destiny.Soon/RAt_last < encountered/Rreached [, and "
        "they/Rthe_twain eyed_each_other/Rmet_each_other's_gaze."
    ),
    Intro.SAIL: "< sailed/Rnavigated > little_ship/Rsloop into the &.",
    Intro.DIVE: (
        "< jack-knifed/Rsplashed into the & and dove/Rsank "
        "deeply/Rinto_the_blue_depths, finally meeting/Rreaching [."
    ),
}
