import pytest
from utils.compatibility import compatible_donor_groups, BLOOD_GROUPS

def test_o_negative_only_from_o_negative():
    assert compatible_donor_groups("O-") == ["O-"]

def test_ab_positive_accepts_all():
    assert set(compatible_donor_groups("AB+")) == set(BLOOD_GROUPS)

def test_a_positive():
    assert set(compatible_donor_groups("A+")) == {"A+", "A-", "O+", "O-"}

def test_o_negative_donates_to_everyone():
    assert all("O-" in compatible_donor_groups(g) for g in BLOOD_GROUPS)

def test_invalid():
    with pytest.raises(ValueError):
        compatible_donor_groups("X+")
