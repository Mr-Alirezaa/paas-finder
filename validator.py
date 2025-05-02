import pandas as pd
import numpy as np
import sys

# Import configuration from config.py
from config import (
    # Day ranges
    MANUAL_DAYS_START, MANUAL_DAYS_END, AUTO_DAYS_START, AUTO_DAYS_END,
    # Shift configuration
    AUTO_SHIFT_TYPES, PEOPLE_PER_SHIFT,
    # Day types
    HIGH_VALUE_DAYS, DAY_NAMES, DAY_TYPES,
    # Eligibility
    EXCLUDE_FOOD_DIVIDERS, MARRIED_EXCLUSION_DAYS, NON_NATIVE_EXCLUSION_DAYS,
    # Constraint configurations
    ENFORCE_MAX_SHIFTS, MAX_SHIFTS_PER_PERSON,
    ENFORCE_SHIFT_TYPE_ID_RANGES, A_SHIFT_MIN_ID, B_SHIFT_MAX_ID,
    ENFORCE_NO_CONSECUTIVE_DAYS,
    ENFORCE_MAX_D_SHIFTS, MAX_D_SHIFTS,
    ENFORCE_MAX_HIGH_VALUE_DAYS, MAX_HIGH_VALUE_DAYS
)

def validate_shifts(input_file='shifts_final.csv'):
    """Validate the generated shifts according to the configured constraints."""
    print(f"Validating shifts in {input_file}...")

    # Read the shifts data
    df = pd.read_csv(input_file, index_col=0)

    # Initialize validation results
    all_valid = True
    total_errors = 0

    # 1. Validate the right number of people per shift
    print("\nChecking people per shift constraint...")
    for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
        for shift_type in AUTO_SHIFT_TYPES:
            shift_count = sum(1 for _, row in df.iterrows()
                             if row.get(f'Day {day}') == shift_type)
            if shift_count != PEOPLE_PER_SHIFT:
                print(f"❌ Day {day}, Shift {shift_type}: Has {shift_count} people instead of {PEOPLE_PER_SHIFT}")
                all_valid = False
                total_errors += 1

    # 2. Validate food divider constraint
    if EXCLUDE_FOOD_DIVIDERS:
        print("\nChecking food divider constraint...")
        for person_id, row in df.iterrows():
            if row['food_divider']:
                for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                    if pd.notna(row.get(f'Day {day}')):
                        print(f"❌ Person {person_id} is a food divider but assigned to shift {row[f'Day {day}']} on Day {day}")
                        all_valid = False
                        total_errors += 1

    # 3. Validate married people exclusion days
    print("\nChecking married people exclusion days...")
    for person_id, row in df.iterrows():
        if row['married']:
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                day_name = DAY_TYPES.get(day)
                if day_name in MARRIED_EXCLUSION_DAYS and pd.notna(row.get(f'Day {day}')):
                    print(f"❌ Person {person_id} is married but assigned on {day_name} (Day {day})")
                    all_valid = False
                    total_errors += 1

    # 4. Validate non-native people exclusion days
    print("\nChecking non-native people exclusion days...")
    for person_id, row in df.iterrows():
        if row['non_native']:
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                day_name = DAY_TYPES.get(day)
                if day_name in NON_NATIVE_EXCLUSION_DAYS and pd.notna(row.get(f'Day {day}')):
                    print(f"❌ Person {person_id} is non-native but assigned on {day_name} (Day {day})")
                    all_valid = False
                    total_errors += 1

    # 5. Validate shift type ID ranges
    if ENFORCE_SHIFT_TYPE_ID_RANGES:
        print("\nChecking shift type ID ranges...")
        for person_id, row in df.iterrows():
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                shift = row.get(f'Day {day}')
                if pd.notna(shift):
                    # Check A shifts
                    if shift == "A" and int(person_id) < A_SHIFT_MIN_ID:
                        print(f"❌ Person {person_id} has ID < {A_SHIFT_MIN_ID} but assigned to A shift on Day {day}")
                        all_valid = False
                        total_errors += 1
                    # Check B shifts
                    if shift == "B" and int(person_id) > B_SHIFT_MAX_ID:
                        print(f"❌ Person {person_id} has ID > {B_SHIFT_MAX_ID} but assigned to B shift on Day {day}")
                        all_valid = False
                        total_errors += 1

    # 6. Validate no consecutive days
    if ENFORCE_NO_CONSECUTIVE_DAYS:
        print("\nChecking no consecutive days constraint...")
        for person_id, row in df.iterrows():
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END):
                if pd.notna(row.get(f'Day {day}')) and pd.notna(row.get(f'Day {day+1}')):
                    print(f"❌ Person {person_id} works consecutive days {day} and {day+1}")
                    all_valid = False
                    total_errors += 1

    # 7. Validate max D shifts
    if ENFORCE_MAX_D_SHIFTS:
        print("\nChecking max D shifts constraint...")
        for person_id, row in df.iterrows():
            # Count D shifts in manual days
            manual_d_shifts = sum(1 for day in range(MANUAL_DAYS_START, MANUAL_DAYS_END + 1)
                                  if row.get(f'Day {day}') == 'D')

            # Count D shifts in auto days
            auto_d_shifts = sum(1 for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)
                               if row.get(f'Day {day}') == 'D')

            total_d_shifts = manual_d_shifts + auto_d_shifts
            if total_d_shifts > MAX_D_SHIFTS:
                print(f"❌ Person {person_id} has {total_d_shifts} D shifts (max: {MAX_D_SHIFTS})")
                all_valid = False
                total_errors += 1

    # 8. Validate max high-value days
    if ENFORCE_MAX_HIGH_VALUE_DAYS:
        print("\nChecking max high-value days constraint...")
        for person_id, row in df.iterrows():
            # Count high-value shifts in manual days
            manual_hv_shifts = sum(1 for day in range(MANUAL_DAYS_START, MANUAL_DAYS_END + 1)
                                  if pd.notna(row.get(f'Day {day}')) and
                                  DAY_NAMES[(day - 1) % 7] in HIGH_VALUE_DAYS)

            # Count high-value shifts in auto days
            auto_hv_shifts = sum(1 for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)
                               if pd.notna(row.get(f'Day {day}')) and
                               DAY_TYPES.get(day) in HIGH_VALUE_DAYS)

            total_hv_shifts = manual_hv_shifts + auto_hv_shifts
            if total_hv_shifts > MAX_HIGH_VALUE_DAYS:
                print(f"❌ Person {person_id} has {total_hv_shifts} high-value day shifts (max: {MAX_HIGH_VALUE_DAYS})")
                all_valid = False
                total_errors += 1

    # 9. Validate max total shifts per person
    if ENFORCE_MAX_SHIFTS:
        print("\nChecking max total shifts constraint...")
        for person_id, row in df.iterrows():
            # Count shifts in manual days
            manual_shifts = sum(1 for day in range(MANUAL_DAYS_START, MANUAL_DAYS_END + 1)
                               if pd.notna(row.get(f'Day {day}')))

            # Count shifts in auto days
            auto_shifts = sum(1 for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)
                             if pd.notna(row.get(f'Day {day}')))

            total_shifts = manual_shifts + auto_shifts
            if total_shifts > MAX_SHIFTS_PER_PERSON:
                print(f"❌ Person {person_id} has {total_shifts} total shifts (max: {MAX_SHIFTS_PER_PERSON})")
                all_valid = False
                total_errors += 1

    # Summary
    if all_valid:
        print("\n✅ All constraints are satisfied!")
    else:
        print(f"\n❌ Found {total_errors} constraint violations")

    return all_valid

if __name__ == "__main__":
    # Allow specifying a different input file
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'shifts_final.csv'
    result = validate_shifts(input_file)
    if not result:
        sys.exit(1)  # Non-zero exit code for failures
