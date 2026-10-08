"""Red-cell compatibility rules. Edit here only; matching imports from this module."""
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# recipient -> donor groups that can give to them
DONORS_FOR = {
    "O-":  ["O-"],
    "O+":  ["O+", "O-"],
    "A-":  ["A-", "O-"],
    "A+":  ["A+", "A-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": list(BLOOD_GROUPS),
}

def compatible_donor_groups(recipient: str) -> list[str]:
    if recipient not in DONORS_FOR:
        raise ValueError(f"Invalid blood group: {recipient}")
    return DONORS_FOR[recipient]
