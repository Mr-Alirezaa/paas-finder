import csv
import pandas as pd
import numpy as np
from ortools.sat.python import cp_model

# Configuration section - Customize these values as needed
SHIFT_SCORES = {
    # Regular days (Sat through Wed)
    "regular": {
        "A": 3.0,
        "B": 3.0,
        "C": 3.0,
        "D": 8.0,
        "E": 4.0
    },
    # High-value days (Thu and Fri)
    "high_value": {
        "A": 12.0,
        "B": 12.0,
        "C": 12.0,
        "D": 12.0,
        "E": 12.0
    }
}

# Define day types and shift scores
DAY_NAMES = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_TYPES = {
    8: "Saturday", 9: "Sunday", 10: "Monday", 11: "Tuesday", 12: "Wednesday",
    13: "Thursday", 14: "Friday", 15: "Saturday", 16: "Sunday", 17: "Monday",
    18: "Tuesday", 19: "Wednesday"
}

def get_shift_score(shift_type, day_name):
    if day_name in ["Thursday", "Friday"]:
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
    for day in range(1, 8):
        col_name = f'Day {day}'
        shift = str(row[col_name]).strip() if pd.notna(row[col_name]) else ''

        if shift:
            day_name = DAY_NAMES[(day - 1) % 7]  # Day 1 is Saturday
            score = get_shift_score(shift, day_name)
            people[person_id]['initial_score'] += score
            people[person_id]['current_assignments'].append((day, shift))

# Filter out food dividers as they shouldn't be assigned shifts
eligible_people = {p_id: p for p_id, p in people.items() if not p['food_divider']}

# Create the constraint model
model = cp_model.CpModel()

# Decision variables: x[person_id][day][shift_type] = 1 if person works that shift on that day
x = {}
for person_id, person in eligible_people.items():
    x[person_id] = {}
    for day in range(8, 20):  # Days 8-19
        x[person_id][day] = {}
        for shift_type in ["A", "B", "D"]:  # Only A, B, D shifts for days 8-19
            x[person_id][day][shift_type] = model.NewBoolVar(f'x_{person_id}_{day}_{shift_type}')

# Track total scores
total_score = {}
shift_count_D = {}  # Track D shifts per person
shift_count_thu_fri = {}  # Track Thu/Fri shifts per person

for person_id, person in eligible_people.items():
    # Initialize from initial scores (days 1-7)
    score_expr = [int(person['initial_score'] * 100)]  # Scale to avoid floating point

    # Track D shifts from initial assignments
    shift_count_D[person_id] = sum(1 for day, shift in person['current_assignments'] if shift == 'D')

    # Track Thursday/Friday shifts from initial assignments
    shift_count_thu_fri[person_id] = sum(1 for day, shift in person['current_assignments']
                                        if DAY_NAMES[(day - 1) % 7] in ["Thursday", "Friday"])

    # Add score contributions from new assignments (days 8-19)
    for day in range(8, 20):
        day_name = DAY_TYPES[day]
        for shift_type in ["A", "B", "D"]:
            score = get_shift_score(shift_type, day_name)
            score_expr.append(x[person_id][day][shift_type] * int(score * 100))  # Scale to avoid floating point

    # Define total score variable
    total_score[person_id] = model.NewIntVar(0, 100000, f'total_score_{person_id}')
    model.Add(total_score[person_id] == sum(score_expr))

# Constraints
for day in range(8, 20):
    day_name = DAY_TYPES[day]

    # Constraint: Exactly 3 people per shift type per day
    for shift_type in ["A", "B", "D"]:
        model.Add(sum(x[person_id][day][shift_type] for person_id in eligible_people) == 3)

    # Constraint: Each person works at most one shift per day
    for person_id in eligible_people:
        model.Add(sum(x[person_id][day][shift_type] for shift_type in ["A", "B", "D"]) <= 1)

    # Constraint: Married and non-native people can't work Wednesday to Friday
    if day_name in ["Wednesday", "Thursday", "Friday"]:
        for person_id, person in eligible_people.items():
            if person['married'] or person['non_native']:
                for shift_type in ["A", "B", "D"]:
                    model.Add(x[person_id][day][shift_type] == 0)

    # Constraint: A shifts only for people with IDs 49-90
    for person_id in eligible_people:
        if person_id < 49:
            model.Add(x[person_id][day]["A"] == 0)

    # Constraint: B shifts only for people with IDs 1-48
    for person_id in eligible_people:
        if person_id > 48:
            model.Add(x[person_id][day]["B"] == 0)

# Constraint: No consecutive days
for person_id in eligible_people:
    for day in range(8, 19):  # Up to day 18 (since we compare with next day)
        # Create a Boolean variable that's true if person works on this day
        works_today = model.NewBoolVar(f'works_today_{person_id}_{day}')
        today_shifts = [x[person_id][day][s] for s in ["A", "B", "D"]]
        tomorrow_shifts = [x[person_id][day+1][s] for s in ["A", "B", "D"]]

        # Link works_today with the sum of today's shifts
        model.Add(sum(today_shifts) >= 1).OnlyEnforceIf(works_today)
        model.Add(sum(today_shifts) == 0).OnlyEnforceIf(works_today.Not())

        # If person works today, they can't work tomorrow
        model.Add(sum(tomorrow_shifts) == 0).OnlyEnforceIf(works_today)

# Constraint: No more than one D shift per person
for person_id, count in shift_count_D.items():
    if count >= 1:
        # Already has a D shift from days 1-7, so can't have any more
        for day in range(8, 20):
            model.Add(x[person_id][day]["D"] == 0)
    else:
        # Can have at most one D shift in days 8-19
        model.Add(sum(x[person_id][day]["D"] for day in range(8, 20)) <= 1)

# Constraint: No more than one Thursday or Friday shift in the period
for person_id, count in shift_count_thu_fri.items():
    if count >= 1:
        # Already has a Thu/Fri shift from days 1-7, so can't have any more high-score days
        for day in range(8, 20):
            if DAY_TYPES[day] in ["Thursday", "Friday"]:
                for shift_type in ["A", "B", "D"]:
                    model.Add(x[person_id][day][shift_type] == 0)
    else:
        # Can have at most one Thu/Fri shift in days 8-19
        thu_fri_days = [day for day in range(8, 20) if DAY_TYPES[day] in ["Thursday", "Friday"]]
        model.Add(sum(x[person_id][day][s] for day in thu_fri_days for s in ["A", "B", "D"]) <= 1)

# Objective: Fairness (minimize deviation from average)
# First, compute the expected average score
total_initial_score = sum(person['initial_score'] for person in people.values())
total_shifts = 3 * 3 * 12  # 3 types × 3 persons × 12 days
avg_score_estimate = (total_initial_score +
                      sum(get_shift_score(s, DAY_TYPES[d]) for d in range(8, 20)
                          for s in ["A", "B", "D"]) * 3) / 90  # Divide by total people
avg_score_scaled = int(avg_score_estimate * 100)

# Define deviation variables
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

# Minimize the sum of absolute deviations (for fairness)
model.Minimize(sum(absolute_deviation.values()))

# Solve the model
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 600  # 10-minute timeout
status = solver.Solve(model)

# Process results
if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print(f"Solution found with status: {solver.StatusName(status)}")

    # Create result dataframe with all days (1-19)
    result_df = pd.DataFrame(index=range(1, 91),
                            columns=[f'Day {i}' for i in range(1, 20)])

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
        for day in range(8, 20):
            for shift_type in ["A", "B", "D"]:
                if solver.Value(x[person_id][day][shift_type]) == 1:
                    result_df.at[person_id, f'Day {day}'] = shift_type

    # Double-check no food dividers got shifts
    for person_id, person in people.items():
        if person['food_divider']:
            for day in range(8, 20):
                if pd.notna(result_df.at[person_id, f'Day {day}']):
                    print(f"ERROR: Food divider {person_id} was assigned a shift on Day {day}")
                    result_df.at[person_id, f'Day {day}'] = np.nan

    # Calculate final scores
    final_scores = {}
    for person_id, person in people.items():
        if person_id in eligible_people:
            score = person['initial_score']
            for day in range(8, 20):
                for shift_type in ["A", "B", "D"]:
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
    print(f"Average score: {sum(final_scores.values()) / len(final_scores):.2f}")
    print(f"Min score: {min(final_scores.values()):.2f}")
    print(f"Max score: {max(final_scores.values()):.2f}")
else:
    print(f"No solution found. Status: {solver.StatusName(status)}")
