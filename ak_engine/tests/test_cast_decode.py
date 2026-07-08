from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ak_engine.models.enums import ActionCode, Spell
from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.cast_decode import CastRequest, decode_cast_phase

GAME_DATA_DIR = Path(__file__).resolve().parents[2]


def _walk_phases(plan):
    for segment in plan.segments:
        for label, phase in segment.phases.items():
            yield label, phase
            if phase.nested_plan is not None:
                yield from _walk_phases(phase.nested_plan)


def test_decode_cast_phase_maps_obj_to_spell_and_extra_to_target():
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=17, extra=[18])

    request = decode_cast_phase(phase)

    assert request == CastRequest(spell=Spell.ILLUS_ARMIES, target=18, terrain=None)


def test_decode_cast_phase_illus_terrain_reads_the_extra_terrain_field():
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=16, extra=[142, 3])

    request = decode_cast_phase(phase)

    assert request.spell == Spell.ILLUS_TERRAIN
    assert request.target == 142
    assert request.terrain == Terrain.FOREST


def test_decode_cast_phase_no_target_spell_has_zero_target():
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=4, extra=[0])

    request = decode_cast_phase(phase)

    assert request.spell == Spell.SKELETAL_ARMY
    assert request.target == 0
    assert request.terrain is None


def test_decode_cast_phase_keeps_out_of_range_spell_raw():
    phase = PlanPhase(label="P0", action=ActionCode.CAST, obj=99, extra=[0])

    request = decode_cast_phase(phase)

    assert request.spell == 99


def test_decode_cast_phase_against_every_real_move_file():
    # Empirical distribution across all 10 sample AK3__T*.K1 files,
    # independently re-verified via the real parser: 108 total real Cast
    # phases, 12 distinct spell ids, every one a documented Action spell
    # (rulebook [3.10]: "must be an Action Spell, not a personal-combat
    # spell") -- never one of the 10 Personal-Combat-only spells.
    expected_counts = {
        Spell.SKELETAL_ARMY: 29,
        Spell.BLESS: 16,
        Spell.CHARM: 12,
        Spell.PLAGUE: 12,
        Spell.RESURRECTION: 11,
        Spell.TORNADO: 7,
        Spell.KILL_ENEMY: 7,
        Spell.ILLUS_ARMIES: 4,
        Spell.FLOOD: 3,
        Spell.ORATORY: 3,
        Spell.ILLUS_TERRAIN: 2,
        Spell.PART_SEA: 2,
    }
    personal_combat_only = {
        Spell.HOLY_SYMBOL,
        Spell.HAND_OF_DEATH,
        Spell.FIREBALL,
        Spell.PSYCHIC_BLAST,
        Spell.INVISIBILITY,
        Spell.SPIRITWRACK,
        Spell.CONTROL_UNDEAD,
        Spell.ICE_SUSPEND,
        Spell.TELEK_STORM,
        Spell.MIRROR_IMAGE,
    }

    counts: Counter[Spell] = Counter()
    targets_by_spell: dict[Spell, list[int]] = defaultdict(list)
    total = 0
    for n in range(1, 11):
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{n}.K1")
        for leader in kingdom.leaders:
            for _label, phase in _walk_phases(leader.plan):
                if phase.action != ActionCode.CAST:
                    continue
                total += 1
                request = decode_cast_phase(phase)
                assert isinstance(request.spell, Spell), (n, leader.leader_id, phase)
                assert request.spell not in personal_combat_only, (n, leader.leader_id, phase)
                counts[request.spell] += 1
                targets_by_spell[request.spell].append(request.target)

    assert total == 108
    assert counts == expected_counts
    # Skeletal Army needs no target per the rulebook -- confirmed exclusive.
    assert targets_by_spell[Spell.SKELETAL_ARMY] == [0] * 29
    assert all(t != 0 for t in targets_by_spell[Spell.BLESS])
