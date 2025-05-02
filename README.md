# Fair Shift Scheduler

A constraint-based shift scheduling system designed to optimize fairness in shift assignments.

## Overview

This project automates the assignment of worker shifts using Google OR-Tools' constraint programming solver to ensure a fair distribution of workload. The system takes manually assigned shifts for an initial period and then optimally assigns shifts for subsequent days, ensuring that various constraints are respected while minimizing the deviation in total score (workload) between workers.

## Features

- **Fairness Optimization**: Minimizes the deviation from average workload across all eligible workers
- **Configurable Constraints**: All constraints can be enabled/disabled and customized
- **Validation**: Includes a validator tool to verify that all constraints are satisfied
- **Detailed Statistics**: Provides comprehensive statistics on the resulting assignments

## Constraints

The system supports the following configurable constraints:

- **Maximum shifts per person**: Limits the total number of shifts any worker can be assigned
- **No consecutive days**: Prevents workers from being assigned shifts on consecutive days
- **Shift type restrictions by ID**: Assigns certain shift types only to specific ID ranges
- **Exclusion days by worker type**: Prevents married or non-native workers from working on specific days
- **Maximum high-value day shifts**: Limits the number of high-value (typically Thu/Fri) shifts per worker
- **Maximum D-shifts**: Limits the number of D-type shifts any worker can be assigned

## Configuration

All constraints and system parameters are configurable in `config.py`:

- Day ranges for manual and auto-assignments
- Shift types and scoring
- Worker eligibility rules
- All constraint parameters

## Running the System

### Prerequisites

- Python 3.6+
- pandas
- numpy
- OR-Tools (`uv add ortools`)

### Input Data

Prepare a `shifts.csv` file with the following columns:
- `person`: Worker ID number
- `food divider`, `non-native`, `married`: Boolean attributes
- `Day 1` through `Day 7`: Initial shift assignments

### Execution

1. Configure the system in `config.py`
2. Run the main scheduler:
   ```
   python main.py
   ```
3. Validate the results:
   ```
   python validator.py
   ```

### Output

The system produces `shifts_final.csv` with all assignments and detailed statistics on the fairness of the distribution.

## File Structure

- `config.py`: All configuration parameters
- `main.py`: The main scheduling algorithm
- `validator.py`: Tool to validate that the solution respects all constraints
- `shifts.csv`: Input data with initial assignments
- `shifts_final.csv`: Output with complete assignments
