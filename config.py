# Configuration section - All parameters for the shift scheduling system

# Day ranges for scheduling
MANUAL_DAYS_START = 1
MANUAL_DAYS_END = 7
AUTO_DAYS_START = 8
AUTO_DAYS_END = 19

# Shift configuration
AUTO_SHIFT_TYPES = ["A", "B", "D"]  # Types of shifts for automatic assignment
PEOPLE_PER_SHIFT = 3  # Number of people assigned to each shift

# Day type configurations
HIGH_VALUE_DAYS = ["Thursday", "Friday"]  # Days with higher shift scores

# Eligibility configurations
EXCLUDE_FOOD_DIVIDERS = True  # Whether to exclude food dividers from shifts
MARRIED_EXCLUSION_DAYS = ["Wednesday", "Thursday", "Friday"]  # Days married people can't work
NON_NATIVE_EXCLUSION_DAYS = ["Wednesday", "Thursday", "Friday"]  # Days non-native people can't work

# Constraint configurations
ENFORCE_MAX_SHIFTS = True  # Whether to enforce the max shifts constraint
MAX_SHIFTS_PER_PERSON = 3  # Maximum total shifts per person (manual + auto periods)

ENFORCE_SHIFT_TYPE_ID_RANGES = True  # Whether to enforce the ID ranges for shift types
A_SHIFT_MIN_ID = 49  # Minimum person ID for A shifts
B_SHIFT_MAX_ID = 48  # Maximum person ID for B shifts

ENFORCE_NO_CONSECUTIVE_DAYS = True  # Whether to enforce the no consecutive days constraint
ENFORCE_MAX_D_SHIFTS = True  # Whether to enforce the max D shifts constraint
MAX_D_SHIFTS = 1  # Maximum D shifts per person

ENFORCE_MAX_HIGH_VALUE_DAYS = True  # Whether to enforce max Thursday/Friday shifts
MAX_HIGH_VALUE_DAYS = 1  # Maximum high-value day shifts per person

SHIFT_SCORES = {
    # Regular days (Sat through Wed)
    "regular": {
        "A": 3.0,
        "B": 3.0,
        "C": 3.0,  # Only used for days 1-7 initial scoring
        "D": 8.0,
        "E": 4.0   # Only used for days 1-7 initial scoring
    },
    # High-value days (Thu and Fri)
    "high_value": {
        "A": 9.0,
        "B": 9.0,
        "C": 9.0,  # Only used for days 1-7 initial scoring
        "D": 9.0,
        "E": 9.0   # Only used for days 1-7 initial scoring
    }
}

# Define day types and shift scores
DAY_NAMES = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_TYPES = {
    8: "Saturday", 9: "Sunday", 10: "Monday", 11: "Tuesday", 12: "Wednesday",
    13: "Thursday", 14: "Friday", 15: "Saturday", 16: "Sunday", 17: "Monday",
    18: "Tuesday", 19: "Wednesday"
}
