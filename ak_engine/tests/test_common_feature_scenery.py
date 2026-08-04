from __future__ import annotations

from ak_engine.models.common_feature_scenery import (
    COMMON_FEATURE_SCENERY_NAME,
    CommonFeatureScenery,
)


def test_common_feature_scenery_has_27_declared_members():
    assert len(CommonFeatureScenery) == 27


def test_common_feature_scenery_name_covers_every_member():
    assert set(COMMON_FEATURE_SCENERY_NAME.keys()) == set(CommonFeatureScenery)


def test_common_feature_scenery_name_verbatim_samples():
    assert COMMON_FEATURE_SCENERY_NAME[CommonFeatureScenery.NONE] == "CFNone"
    assert COMMON_FEATURE_SCENERY_NAME[CommonFeatureScenery.SEAWEED] == "Seaweed"
    assert COMMON_FEATURE_SCENERY_NAME[CommonFeatureScenery.WELL] == "Well"


def test_common_feature_scenery_ordinals_are_positional():
    assert CommonFeatureScenery.NONE.value == 0
    assert CommonFeatureScenery.SEAWEED.value == 1
    assert CommonFeatureScenery.WELL.value == 26


def test_common_feature_scenery_is_distinct_from_magic_feature():
    # Two independent CTME.PAS enums (comfeat vs magfeat) -- see module
    # docstring. Confirm they aren't accidentally the same type.
    from ak_engine.models.magic_feature import MagicFeature

    assert CommonFeatureScenery is not MagicFeature
    assert CommonFeatureScenery.SEAWEED not in list(MagicFeature)
