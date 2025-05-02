import pandas as pd
import numpy as np
from ortools.sat.python import cp_model

# Import configurations
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
    ENFORCE_MAX_HIGH_VALUE_DAYS, MAX_HIGH_VALUE_DAYS,
    # Scoring
    SHIFT_SCORES
)

def get_shift_score(shift_type, day_name):
    if day_name in HIGH_VALUE_DAYS:
        return SHIFT_SCORES["high_value"].get(shift_type, 0)
    else:
        return SHIFT_SCORES["regular"].get(shift_type, 0)

# Load person data and initial shifts
df = pd.read_csv('shifts.csv')

# Initialize people data structure
people = {}
for i, row in df.iterrows():
    person_id = int(row['person'])
    if person_id > 90:  # Ensure we only have people 1-90
        continue

    people[person_id] = {
        'food_divider': str(row['food divider']).upper() == 'TRUE',
        'non_native': str(row['non-native']).upper() == 'TRUE',
        'married': str(row['married']).upper() == 'TRUE',
        'current_assignments': [],
        'initial_score': 0.0
    }

    # Process initial shifts (days 1-7)
    for day in range(MANUAL_DAYS_START, MANUAL_DAYS_END + 1):
        col_name = f'Day {day}'
        shift = str(row[col_name]).strip() if pd.notna(row[col_name]) else ''

        if shift:
            day_name = DAY_NAMES[(day - 1) % 7]  # Day 1 is Saturday
            score = get_shift_score(shift, day_name)
            people[person_id]['initial_score'] += score
            people[person_id]['current_assignments'].append((day, shift))

# Filter out food dividers if configured to do so
if EXCLUDE_FOOD_DIVIDERS:
    eligible_people = {p_id: p for p_id, p in people.items() if not p['food_divider']}
else:
    eligible_people = people.copy()

# Create the constraint model
model = cp_model.CpModel()

# Decision variables: x[person_id][day][shift_type] = 1 if person works that shift on that day
x = {}
for person_id, person in eligible_people.items():
    x[person_id] = {}
    for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):  # Days 8-19
        x[person_id][day] = {}
        for shift_type in AUTO_SHIFT_TYPES:  # Only A, B, D shifts for days 8-19
            x[person_id][day][shift_type] = model.NewBoolVar(f'x_{person_id}_{day}_{shift_type}')

# Track total scores
total_score = {}
shift_count_D = {}  # Track D shifts per person
shift_count_thu_fri = {}  # Track high-value day shifts per person
initial_shift_count = {}  # Track total initial shifts per person

for person_id, person in eligible_people.items():
    # Initialize from initial scores (days 1-7)
    score_expr = [int(person['initial_score'] * 100)]  # Scale to avoid floating point

    # Track D shifts from initial assignments
    shift_count_D[person_id] = sum(1 for day, shift in person['current_assignments'] if shift == 'D')

    # Track high-value day shifts from initial assignments
    shift_count_thu_fri[person_id] = sum(1 for day, shift in person['current_assignments']
                                        if DAY_NAMES[(day - 1) % 7] in HIGH_VALUE_DAYS)

    # Track total shifts from initial assignments
    initial_shift_count[person_id] = len(person['current_assignments'])

    # Add score contributions from new assignments (days 8-19)
    for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
        day_name = DAY_TYPES[day]
        for shift_type in AUTO_SHIFT_TYPES:
            score = get_shift_score(shift_type, day_name)
            score_expr.append(x[person_id][day][shift_type] * int(score * 100))  # Scale to avoid floating point

    # Define total score variable
    total_score[person_id] = model.NewIntVar(0, 100000, f'total_score_{person_id}')
    model.Add(total_score[person_id] == sum(score_expr))

# Constraints
for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
    day_name = DAY_TYPES[day]

    # Constraint: Exactly PEOPLE_PER_SHIFT people per shift type per day
    for shift_type in AUTO_SHIFT_TYPES:
        model.Add(sum(x[person_id][day][shift_type] for person_id in eligible_people) == PEOPLE_PER_SHIFT)

    # Constraint: Each person works at most one shift per day
    for person_id in eligible_people:
        model.Add(sum(x[person_id][day][shift_type] for shift_type in AUTO_SHIFT_TYPES) <= 1)

    # Constraint: Married people can't work on specific days
    if day_name in MARRIED_EXCLUSION_DAYS:
        for person_id, person in eligible_people.items():
            if person['married']:
                for shift_type in AUTO_SHIFT_TYPES:
                    model.Add(x[person_id][day][shift_type] == 0)

    # Constraint: Non-native people can't work on specific days
    if day_name in NON_NATIVE_EXCLUSION_DAYS:
        for person_id, person in eligible_people.items():
            if person['non_native']:
                for shift_type in AUTO_SHIFT_TYPES:
                    model.Add(x[person_id][day][shift_type] == 0)

    # Constraint: A shifts only for people with IDs A_SHIFT_MIN_ID and above
    if ENFORCE_SHIFT_TYPE_ID_RANGES:
        for person_id in eligible_people:
            if person_id < A_SHIFT_MIN_ID:
                model.Add(x[person_id][day]["A"] == 0)

        # Constraint: B shifts only for people with IDs up to B_SHIFT_MAX_ID
        for person_id in eligible_people:
            if person_id > B_SHIFT_MAX_ID:
                model.Add(x[person_id][day]["B"] == 0)

# Constraint: No consecutive days
if ENFORCE_NO_CONSECUTIVE_DAYS:
    for person_id in eligible_people:
        # Check if the person worked on day 7 (to bridge from manual to auto-assigned period)
        worked_day_7 = False
        for day, shift in eligible_people[person_id]['current_assignments']:
            if day == MANUAL_DAYS_END:
                worked_day_7 = True
                break

        # If person worked on the last manual day, they can't work on the first auto day
        if worked_day_7:
            for shift_type in AUTO_SHIFT_TYPES:
                model.Add(x[person_id][AUTO_DAYS_START][shift_type] == 0)

        # Continue with the regular consecutive days constraint for auto days
        for day in range(AUTO_DAYS_START, AUTO_DAYS_END):  # Up to second-last day (since we compare with next day)
            # Create a Boolean variable that's true if person works on this day
            works_today = model.NewBoolVar(f'works_today_{person_id}_{day}')
            today_shifts = [x[person_id][day][s] for s in AUTO_SHIFT_TYPES]
            tomorrow_shifts = [x[person_id][day+1][s] for s in AUTO_SHIFT_TYPES]

            # Link works_today with the sum of today's shifts
            model.Add(sum(today_shifts) >= 1).OnlyEnforceIf(works_today)
            model.Add(sum(today_shifts) == 0).OnlyEnforceIf(works_today.Not())

            # If person works today, they can't work tomorrow
            model.Add(sum(tomorrow_shifts) == 0).OnlyEnforceIf(works_today)

# Constraint: No more than one D shift per person
if ENFORCE_MAX_D_SHIFTS:
    for person_id, count in shift_count_D.items():
        if count >= MAX_D_SHIFTS:
            # Already has a D shift from days 1-7, so can't have any more
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                model.Add(x[person_id][day]["D"] == 0)
        else:
            # Can have at most MAX_D_SHIFTS - count D shifts in days 8-19
            model.Add(sum(x[person_id][day]["D"] for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)) <= MAX_D_SHIFTS - count)

# Constraint: No more than one Thursday or Friday shift in the period
if ENFORCE_MAX_HIGH_VALUE_DAYS:
    for person_id, count in shift_count_thu_fri.items():
        if count >= MAX_HIGH_VALUE_DAYS:
            # Already has max high-value shifts from days 1-7, so can't have any more high-score days
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                if DAY_TYPES[day] in HIGH_VALUE_DAYS:
                    for shift_type in AUTO_SHIFT_TYPES:
                        model.Add(x[person_id][day][shift_type] == 0)
        else:
            # Can have at most MAX_HIGH_VALUE_DAYS - count high-value shifts in days 8-19
            high_value_days = [day for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1) if DAY_TYPES[day] in HIGH_VALUE_DAYS]
            model.Add(sum(x[person_id][day][s] for day in high_value_days for s in AUTO_SHIFT_TYPES) <= MAX_HIGH_VALUE_DAYS - count)

# Constraint: Maximum shifts per person across the entire period
if ENFORCE_MAX_SHIFTS:
    for person_id, initial_count in initial_shift_count.items():
        remaining_shifts = MAX_SHIFTS_PER_PERSON - initial_count
        if remaining_shifts <= 0:
            # Person has already reached or exceeded their maximum shifts, don't assign any more
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                for shift_type in AUTO_SHIFT_TYPES:
                    model.Add(x[person_id][day][shift_type] == 0)
        else:
            # Person can have at most remaining_shifts more shifts
            model.Add(sum(x[person_id][day][s]
                          for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)
                          for s in AUTO_SHIFT_TYPES) <= remaining_shifts)

# Objective: Fairness (minimize deviation from average)
# Calculate average using only eligible people (excluding food dividers)
total_initial_score_eligible = sum(person['initial_score'] for person in eligible_people.values())
num_eligible_people = len(eligible_people)

# Calculate total score from new shifts
total_shifts = PEOPLE_PER_SHIFT * len(AUTO_SHIFT_TYPES) * (AUTO_DAYS_END - AUTO_DAYS_START + 1)  # people × types × days
avg_score_estimate = (total_initial_score_eligible +
                      sum(get_shift_score(s, DAY_TYPES[d]) for d in range(AUTO_DAYS_START, AUTO_DAYS_END + 1)
                          for s in AUTO_SHIFT_TYPES) * PEOPLE_PER_SHIFT) / num_eligible_people  # Divide by eligible people
avg_score_scaled = int(avg_score_estimate * 100)

# Define deviation variables - only for eligible people
deviation_up = {}
deviation_down = {}
absolute_deviation = {}

for person_id in eligible_people:
    deviation_up[person_id] = model.NewIntVar(0, 100000, f'dev_up_{person_id}')
    deviation_down[person_id] = model.NewIntVar(0, 100000, f'dev_down_{person_id}')
    absolute_deviation[person_id] = model.NewIntVar(0, 100000, f'abs_dev_{person_id}')

    # Link variables: absolute_deviation = max(total_score - avg, avg - total_score)
    model.Add(total_score[person_id] - avg_score_scaled <= deviation_up[person_id])
    model.Add(avg_score_scaled - total_score[person_id] <= deviation_down[person_id])
    model.Add(absolute_deviation[person_id] == deviation_up[person_id] + deviation_down[person_id])

# Minimize the sum of absolute deviations (for fairness) - only for eligible people
model.Minimize(sum(absolute_deviation.values()))

# Solve the model
solver = cp_model.CpSolver()

# Set parameters to prioritize finding the optimal solution
solver.parameters.max_time_in_seconds = 1000  # 0 means no time limit
solver.parameters.num_search_workers = 8  # Use more threads if available on your system
solver.parameters.log_search_progress = True  # Log progress to console
solver.parameters.cp_model_presolve = True  # Enable presolve (default)
solver.parameters.linearization_level = 2  # More aggressive linearization (0-2)
solver.parameters.enumerate_all_solutions = False  # Focus on best solution

print("Starting optimization. This may take a while...")
status = solver.Solve(model)

# Process results
if status == cp_model.OPTIMAL:
    print(f"OPTIMAL solution found! The absolute best score distribution has been achieved.")
elif status == cp_model.FEASIBLE:
    print(f"FEASIBLE solution found, but optimality not proven. There might be a better solution.")
else:
    print(f"No solution found. Status: {solver.StatusName(status)}")
    exit(1)

# If we have any solution (OPTIMAL or FEASIBLE), process it
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    # Create result dataframe with all days (1-19)
    result_df = pd.DataFrame(index=range(1, 91),
                            columns=[f'Day {i}' for i in range(MANUAL_DAYS_START, AUTO_DAYS_END + 1)])

    # Add person attributes for verification
    result_df['food_divider'] = False
    result_df['non_native'] = False
    result_df['married'] = False

    # Fill in person attributes
    for person_id, person in people.items():
        result_df.at[person_id, 'food_divider'] = person['food_divider']
        result_df.at[person_id, 'non_native'] = person['non_native']
        result_df.at[person_id, 'married'] = person['married']

        # Fill in initial assignments (days 1-7)
        for day, shift in person['current_assignments']:
            result_df.at[person_id, f'Day {day}'] = shift

    # Fill in the new assignments (days 8-19)
    for person_id in eligible_people:
        for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
            for shift_type in AUTO_SHIFT_TYPES:
                if solver.Value(x[person_id][day][shift_type]) == 1:
                    result_df.at[person_id, f'Day {day}'] = shift_type

    # Double-check no food dividers got shifts
    for person_id, person in people.items():
        if person['food_divider']:
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                if pd.notna(result_df.at[person_id, f'Day {day}']):
                    print(f"ERROR: Food divider {person_id} was assigned a shift on Day {day}")
                    result_df.at[person_id, f'Day {day}'] = np.nan

    # Calculate final scores for all people (including food dividers)
    final_scores = {}
    for person_id, person in people.items():
        if person_id in eligible_people:
            score = person['initial_score']
            for day in range(AUTO_DAYS_START, AUTO_DAYS_END + 1):
                for shift_type in AUTO_SHIFT_TYPES:
                    if person_id in x and day in x[person_id] and shift_type in x[person_id][day]:
                        if solver.Value(x[person_id][day][shift_type]) == 1:
                            score += get_shift_score(shift_type, DAY_TYPES[day])
            final_scores[person_id] = score
        else:
            final_scores[person_id] = person['initial_score']  # Food dividers keep initial score

    # Add score column
    result_df['Total Score'] = pd.Series(final_scores)

    # Save to CSV
    result_df.to_csv('shifts_final.csv')
    print(f"Results saved to shifts_final.csv")

    # Calculate and display statistics separately for eligible and all people
    eligible_scores = [final_scores[p_id] for p_id in eligible_people]
    all_scores = list(final_scores.values())

    print(f"Stats for eligible people (excluding food dividers):")
    print(f"  Average score: {sum(eligible_scores) / len(eligible_scores):.2f}")
    print(f"  Min score: {min(eligible_scores):.2f}")
    print(f"  Max score: {max(eligible_scores):.2f}")
    print(f"  Standard deviation: {np.std(eligible_scores):.2f}")

    print(f"\nStats for all people (including food dividers):")
    print(f"  Average score: {sum(all_scores) / len(all_scores):.2f}")
    print(f"  Min score: {min(all_scores):.2f}")
    print(f"  Max score: {max(all_scores):.2f}")
    print(f"  Standard deviation: {np.std(all_scores):.2f}")
