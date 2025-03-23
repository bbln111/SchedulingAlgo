#!/usr/bin/env python3
"""
Improved Appointment Scheduler using Google's CP-SAT Solver

A comprehensive scheduling solution that handles multiple appointment types
while respecting various constraints.
"""

import argparse
import datetime
import json
import logging
import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("Error: Google OR-Tools is required. Install with: pip install ortools")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")


class AppointmentType(Enum):
    """Enum for different appointment types."""
    STREETS = "streets"
    TRIAL_STREETS = "trial_streets"
    ZOOM = "zoom"
    TRIAL_ZOOM = "trial_zoom"

    @property
    def is_streets_type(self) -> bool:
        """Check if appointment type is a streets type."""
        return self in (AppointmentType.STREETS, AppointmentType.TRIAL_STREETS)

    @property
    def is_zoom_type(self) -> bool:
        """Check if appointment type is a zoom type."""
        return self in (AppointmentType.ZOOM, AppointmentType.TRIAL_ZOOM)

    @classmethod
    def from_string(cls, value: str) -> 'AppointmentType':
        """Create an AppointmentType from a string."""
        value = value.lower()
        for appointment_type in cls:
            if appointment_type.value == value:
                return appointment_type
        raise ValueError(f"Invalid appointment type: {value}")


class Priority(Enum):
    """Enum for appointment priority levels."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    EXCLUDE = "Exclude"

    @classmethod
    def from_string(cls, value: str) -> 'Priority':
        """Create a Priority from a string."""
        value = value.capitalize()
        for priority in cls:
            if priority.value == value:
                return priority
        raise ValueError(f"Invalid priority: {value}")


@dataclass
class TimeSlot:
    """Represents a time slot with start and end times."""
    start_time: datetime.datetime
    end_time: datetime.datetime

    def __post_init__(self):
        """Validate the time slot."""
        if self.start_time >= self.end_time:
            raise ValueError(f"Start time {self.start_time} is not before end time {self.end_time}")


@dataclass
class Availability:
    """Represents availability on a specific day."""
    day: str
    time_slots: List[TimeSlot]


@dataclass
class Appointment:
    """Represents an appointment request."""
    id: str
    priority: Priority
    appointment_type: AppointmentType
    duration_minutes: int
    availabilities: List[Availability]

    @classmethod
    def from_dict(cls, data: Dict) -> 'Appointment':
        """Create an Appointment from a dictionary."""
        logger.debug(f"Creating appointment from: {data}")

        # Extract basic information
        appointment_id = data.get("id")
        priority = Priority.from_string(data.get("priority"))
        appointment_type = AppointmentType.from_string(data.get("type"))
        duration_minutes = int(data.get("time"))

        # Process availabilities
        availabilities = []
        for day_data in data.get("days", []):
            day = day_data.get("day")
            time_slots = []

            for time_frame in day_data.get("time_frames", []):
                try:
                    start_time = datetime.datetime.fromisoformat(time_frame.get("start"))
                    end_time = datetime.datetime.fromisoformat(time_frame.get("end"))
                    time_slots.append(TimeSlot(start_time, end_time))
                except ValueError as e:
                    logger.warning(f"Invalid time frame for appointment {appointment_id} on {day}: {e}")

            availabilities.append(Availability(day, time_slots))

        return cls(
            id=appointment_id,
            priority=priority,
            appointment_type=appointment_type,
            duration_minutes=duration_minutes,
            availabilities=availabilities
        )


@dataclass
class ScheduledAppointment:
    """Represents a scheduled appointment."""
    appointment_id: str
    appointment_type: AppointmentType
    duration_minutes: int
    start_time: datetime.datetime
    end_time: datetime.datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": self.appointment_id,
            "type": self.appointment_type.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes
        }


def day_name_to_weekday(day_name: str) -> int:
    """Convert day name to weekday number (0=Monday, 1=Tuesday, ..., 6=Sunday)."""
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    return days.get(day_name.lower(), -1)


def weekday_to_day_name(weekday: int) -> str:
    """Convert weekday number to day name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[weekday % 7]


class AppointmentScheduler:
    """
    Appointment scheduler using Google's CP-SAT solver.
    Schedules appointments while respecting various constraints.
    """

    # Scheduling constraints
    MIN_BREAK_MINUTES = 15  # Minimum break between any two appointments
    MIN_BREAK_BETWEEN_TYPES_MINUTES = 75  # Minimum break between different types
    MIN_STREETS_SESSIONS_PER_DAY = 2  # Minimum streets sessions per day, if any
    MAX_STREETS_MINUTES_PER_DAY = 270  # Maximum minutes of streets sessions per day
    MAX_GAP_BETWEEN_STREETS_MINUTES = 30  # Maximum gap between consecutive streets sessions

    # Working hours
    WEEKDAY_START_TIME = datetime.time(10, 0)  # 10:00 AM
    WEEKDAY_END_TIME = datetime.time(23, 15)  # 11:15 PM
    FRIDAY_START_TIME = datetime.time(12, 30)  # 12:30 PM
    FRIDAY_END_TIME = datetime.time(17, 0)  # 5:00 PM

    def __init__(self, start_date: datetime.date):
        """Initialize scheduler with start date."""
        self.start_date = start_date
        self.appointments: List[Appointment] = []
        self.scheduled_appointments: List[ScheduledAppointment] = []
        logger.info(f"Initialized scheduler with start date: {start_date}")

    def add_appointment(self, appointment: Appointment) -> None:
        """Add an appointment to be scheduled."""
        if appointment.priority == Priority.EXCLUDE:
            logger.info(f"Excluding appointment with ID {appointment.id} due to priority 'Exclude'")
            return

        # Validate appointment for scheduling
        if self._validate_appointment(appointment):
            self.appointments.append(appointment)
            logger.info(f"Added appointment with ID {appointment.id} to be scheduled")
        else:
            logger.warning(f"Appointment with ID {appointment.id} failed validation, not added")

    def _validate_appointment(self, appointment: Appointment) -> bool:
        """Validate appointment for scheduling."""
        # Check if there are any availabilities
        if not appointment.availabilities:
            logger.warning(f"Appointment {appointment.id} has no availabilities")
            return False

        # Check if there are any time slots
        has_time_slots = any(len(avail.time_slots) > 0 for avail in appointment.availabilities)
        if not has_time_slots:
            logger.warning(f"Appointment {appointment.id} has no time slots in any availability")
            return False

        # Check if appointment duration is valid
        if appointment.duration_minutes <= 0:
            logger.warning(f"Appointment {appointment.id} has invalid duration: {appointment.duration_minutes}")
            return False

        return True

    def schedule(self) -> List[ScheduledAppointment]:
        """Schedule appointments using CP-SAT solver."""
        logger.info("Starting appointment scheduling")

        if not self.appointments:
            logger.warning("No appointments to schedule")
            return []

        # Group appointments by day
        appointments_by_day = self._group_appointments_by_day()

        # Track scheduled clients across all days
        self.scheduled_client_ids = set()

        # Track scheduled clients by day (for validation)
        scheduled_clients_by_day = {}

        # Process each day separately
        for day_date, day_appointments in appointments_by_day.items():
            logger.info(f"Scheduling for day: {day_date}")

            # Filter out appointments for clients already scheduled on other days
            filtered_appointments = [app for app in day_appointments if app.id not in self.scheduled_client_ids]

            # Log if any appointments were filtered out
            if len(filtered_appointments) < len(day_appointments):
                logger.info(
                    f"Filtered out {len(day_appointments) - len(filtered_appointments)} appointments for clients already scheduled on other days")

            day_appointments = filtered_appointments

            # Log the types of appointments available for this day
            streets_count = sum(1 for app in day_appointments if app.appointment_type.is_streets_type)
            zoom_count = sum(1 for app in day_appointments if app.appointment_type.is_zoom_type)
            logger.info(f"Available for {day_date}: {streets_count} streets and {zoom_count} zoom sessions")

            day_schedule = self._schedule_day(day_date, day_appointments)

            if day_schedule:
                # Track which clients were scheduled today
                scheduled_clients_by_day[day_date] = set(app.appointment_id for app in day_schedule)

                # Add to global scheduled clients set
                for app in day_schedule:
                    self.scheduled_client_ids.add(app.appointment_id)

                self.scheduled_appointments.extend(day_schedule)

                # Log successful scheduling
                streets_scheduled = sum(1 for app in day_schedule if app.appointment_type.is_streets_type)
                zoom_scheduled = sum(1 for app in day_schedule if app.appointment_type.is_zoom_type)
                logger.info(f"Scheduled for {day_date}: {streets_scheduled} streets and {zoom_scheduled} zoom sessions")
            else:
                logger.warning(f"No appointments scheduled for {day_date}")

        logger.info(f"Scheduling complete, {len(self.scheduled_appointments)} appointments scheduled")

        # Log the final schedule by appointment type
        streets_scheduled = sum(1 for app in self.scheduled_appointments if app.appointment_type.is_streets_type)
        zoom_scheduled = sum(1 for app in self.scheduled_appointments if app.appointment_type.is_zoom_type)
        logger.info(f"Final schedule: {streets_scheduled} streets and {zoom_scheduled} zoom sessions")

        return self.scheduled_appointments

    def _group_appointments_by_day(self) -> Dict[datetime.date, List[Appointment]]:
        """Group appointments by day based on the actual date in time slots."""
        appointments_by_day = {}

        # Process each appointment
        for appointment in self.appointments:
            # Extract all unique dates from the appointment's time slots
            dates = set()
            for availability in appointment.availabilities:
                for time_slot in availability.time_slots:
                    dates.add(time_slot.start_time.date())

            # Add appointment to each day's group
            for date in dates:
                if date not in appointments_by_day:
                    appointments_by_day[date] = []
                appointments_by_day[date].append(appointment)

        return appointments_by_day

    def _get_appointment_availability(self, appointment: Appointment, date: datetime.date) -> List[TimeSlot]:
        """Get appointment availability for a specific date based on actual time slot dates."""
        date_slots = []

        # Iterate through all availabilities
        for availability in appointment.availabilities:
            for slot in availability.time_slots:
                # Check if the time slot is for the target date
                slot_date = slot.start_time.date()
                if slot_date == date:
                    # Add this slot to our results
                    date_slots.append(slot)

        return date_slots

    def get_valid_time_ranges(self, date: datetime.date) -> List[Tuple[datetime.datetime, datetime.datetime]]:
        """Get valid time ranges for scheduling based on working hours."""
        # Determine if the day is Friday
        is_friday = date.weekday() == 4  # 4 = Friday

        # Set appropriate start and end times
        if is_friday:
            start_time = self.FRIDAY_START_TIME
            end_time = self.FRIDAY_END_TIME
        else:
            start_time = self.WEEKDAY_START_TIME
            end_time = self.WEEKDAY_END_TIME

        # Combine date and times
        valid_start = datetime.datetime.combine(date, start_time)
        valid_end = datetime.datetime.combine(date, end_time)

        return [(valid_start, valid_end)]

    def _schedule_day(self, date: datetime.date, appointments: List[Appointment]) -> List[ScheduledAppointment]:
        """Schedule appointments for a specific day."""
        logger.info(f"Setting up CP-SAT model for {date}")

        # Create the model
        model = cp_model.CpModel()

        # Get valid time ranges
        valid_time_ranges = self.get_valid_time_ranges(date)
        if not valid_time_ranges:
            logger.warning(f"No valid time ranges for {date}")
            return []

        # Discretize the day into minutes
        day_start = valid_time_ranges[0][0]
        day_end = valid_time_ranges[-1][1]
        total_minutes = int((day_end - day_start).total_seconds() / 60)

        logger.debug(f"Day schedule range: {day_start} to {day_end} ({total_minutes} minutes)")

        # Prepare variables to track appointments
        appointment_vars = {}  # Maps appointment ID to CP-SAT variable
        is_scheduled = {}  # Maps appointment ID to boolean variable indicating if it's scheduled
        appointment_durations = {}  # Maps appointment ID to duration
        appointment_types = {}  # Maps appointment ID to type
        appointment_client_ids = {}  # Maps appointment ID to client ID

        # Track appointments by type
        streets_appointments = []
        zoom_appointments = []

        # Initialize variables for each appointment
        for appointment in appointments:
            # Get availability for this day
            availability = self._get_appointment_availability(appointment, date)
            if not availability:
                logger.debug(f"Appointment {appointment.id} has no availability on {date}")
                continue

            # Create variable for appointment start time
            var_name = f"appointment_{appointment.id}_start"
            # Will use -1 to indicate unscheduled
            start_var = model.NewIntVar(-1, total_minutes, var_name)

            # Boolean variable indicating if this appointment is scheduled
            is_sched_var = model.NewBoolVar(f"is_{appointment.id}_scheduled")

            # Link start time to is_scheduled
            model.Add(start_var >= 0).OnlyEnforceIf(is_sched_var)
            model.Add(start_var == -1).OnlyEnforceIf(is_sched_var.Not())

            # Store appointment info
            appointment_vars[appointment.id] = start_var
            is_scheduled[appointment.id] = is_sched_var
            appointment_durations[appointment.id] = appointment.duration_minutes
            appointment_types[appointment.id] = appointment.appointment_type
            appointment_client_ids[appointment.id] = appointment.id  # Client ID is same as appointment ID

            # Track by appointment type
            if appointment.appointment_type.is_streets_type:
                streets_appointments.append(appointment.id)
            elif appointment.appointment_type.is_zoom_type:
                zoom_appointments.append(appointment.id)

            # Availability constraints - appointment must fit in one of the available slots
            slot_constraints = []

            # First check if any slots overlap working hours
            has_valid_slots = False

            for slot in availability:
                # Skip slots entirely outside working hours
                if slot.end_time <= day_start or slot.start_time >= day_end:
                    logger.debug(f"Slot {slot.start_time} - {slot.end_time} is outside working hours")
                    continue

                # Adjust slot times to fit within working hours if needed
                adjusted_start = max(slot.start_time, day_start)
                adjusted_end = min(slot.end_time, day_end)

                # Skip if adjusted slot is too small for the appointment
                if (adjusted_end - adjusted_start).total_seconds() / 60 < appointment.duration_minutes:
                    logger.debug(f"Adjusted slot too small for appointment {appointment.id}")
                    continue

                has_valid_slots = True

                # Convert to minutes from day start
                slot_start_min = int((adjusted_start - day_start).total_seconds() / 60)
                slot_end_min = int((adjusted_end - day_start).total_seconds() / 60)

                # Create constraint for this slot
                in_slot = model.NewBoolVar(f"{var_name}_in_slot_{slot_start_min}")
                model.Add(start_var >= slot_start_min).OnlyEnforceIf(in_slot)
                model.Add(start_var + appointment.duration_minutes <= slot_end_min).OnlyEnforceIf(in_slot)

                slot_constraints.append(in_slot)

            # If no valid slots, force this appointment to be unscheduled
            if not has_valid_slots:
                logger.warning(f"No valid time slots for appointment {appointment.id} on {date}")
                model.Add(is_sched_var == 0)
            elif slot_constraints:
                # Appointment must fit in one of the available slots if scheduled
                model.AddBoolOr(slot_constraints).OnlyEnforceIf(is_sched_var)
            else:
                # Safety check - should not happen if has_valid_slots is true
                logger.error(f"Logic error: has_valid_slots is true but no slot_constraints for {appointment.id}")
                model.Add(is_sched_var == 0)

        # If no valid appointments, return empty list
        if not appointment_vars:
            logger.info(f"No valid appointments for {date}")
            return []

        # Log available appointments by type
        streets_count = len(streets_appointments)
        zoom_count = len(zoom_appointments)
        logger.info(f"Valid appointments for model on {date}: {streets_count} streets and {zoom_count} zoom sessions")

        # CONSTRAINT 1: One appointment per client per day
        client_to_appointments = {}
        for app_id, client_id in appointment_client_ids.items():
            if client_id not in client_to_appointments:
                client_to_appointments[client_id] = []
            client_to_appointments[client_id].append(app_id)

        for client_id, app_ids in client_to_appointments.items():
            if len(app_ids) > 1:
                # At most one appointment per client
                model.Add(sum(is_scheduled[app_id] for app_id in app_ids) <= 1)

        # CONSTRAINT 2: Non-overlap with minimum breaks between appointments
        appointment_ids = list(appointment_vars.keys())
        for i, id1 in enumerate(appointment_ids):
            for j, id2 in enumerate(appointment_ids):
                if i < j:  # Process each pair once
                    # Skip if same client (already handled by one-appointment-per-client constraint)
                    if appointment_client_ids[id1] == appointment_client_ids[id2]:
                        continue

                    # Determine minimum break required
                    min_break = self.MIN_BREAK_MINUTES

                    # If one is zoom type and the other is streets type, use extended break
                    if ((appointment_types[id1].is_zoom_type and appointment_types[id2].is_streets_type) or
                            (appointment_types[id1].is_streets_type and appointment_types[id2].is_zoom_type)):
                        min_break = self.MIN_BREAK_BETWEEN_TYPES_MINUTES

                    # Both appointments scheduled?
                    both_scheduled = model.NewBoolVar(f"both_{id1}_{id2}_scheduled")
                    model.AddBoolAnd([is_scheduled[id1], is_scheduled[id2]]).OnlyEnforceIf(both_scheduled)
                    model.AddBoolOr([is_scheduled[id1].Not(), is_scheduled[id2].Not()]).OnlyEnforceIf(
                        both_scheduled.Not())

                    # If both scheduled, ensure they don't overlap with proper breaks
                    id1_before_id2 = model.NewBoolVar(f"{id1}_before_{id2}")
                    id2_before_id1 = model.NewBoolVar(f"{id2}_before_{id1}")

                    # If both scheduled, exactly one ordering must be true
                    model.Add(id1_before_id2 + id2_before_id1 == 1).OnlyEnforceIf(both_scheduled)

                    # Order between the appointments
                    model.Add(
                        appointment_vars[id1] + appointment_durations[id1] + min_break <= appointment_vars[id2]
                    ).OnlyEnforceIf([both_scheduled, id1_before_id2])

                    model.Add(
                        appointment_vars[id2] + appointment_durations[id2] + min_break <= appointment_vars[id1]
                    ).OnlyEnforceIf([both_scheduled, id2_before_id1])

        # CONSTRAINT 3 & 4: Streets-specific constraints
        # Either 0 or at least MIN_STREETS_SESSIONS_PER_DAY streets sessions per day
        if streets_appointments:
            streets_scheduled_count = sum(is_scheduled[app_id] for app_id in streets_appointments)

            # Variable indicating if any streets appointments are scheduled
            has_any_streets = model.NewBoolVar("has_any_streets_appointments")
            model.Add(streets_scheduled_count >= 1).OnlyEnforceIf(has_any_streets)
            model.Add(streets_scheduled_count == 0).OnlyEnforceIf(has_any_streets.Not())

            # If we have enough streets sessions available, enforce minimum
            if len(streets_appointments) >= self.MIN_STREETS_SESSIONS_PER_DAY:
                # If any streets are scheduled, at least MIN_STREETS_SESSIONS_PER_DAY must be scheduled
                model.Add(streets_scheduled_count >= self.MIN_STREETS_SESSIONS_PER_DAY).OnlyEnforceIf(has_any_streets)
            else:
                # Not enough streets sessions available to meet minimum
                model.Add(streets_scheduled_count == 0)
                logger.warning(f"Not enough street sessions available on {date} to meet minimum requirement")

            # Maximum total streets minutes per day constraint
            total_streets_minutes = sum(is_scheduled[app_id] * appointment_durations[app_id]
                                        for app_id in streets_appointments)
            model.Add(total_streets_minutes <= self.MAX_STREETS_MINUTES_PER_DAY)

            # FIXED CONSTRAINT: Maximum gap between consecutive streets sessions
            if len(streets_appointments) >= 2:
                # Simply prohibit scheduling streets sessions with gaps > MAX_GAP_BETWEEN_STREETS_MINUTES
                for i, id1 in enumerate(streets_appointments):
                    for j, id2 in enumerate(streets_appointments):
                        if i < j:
                            # Create a direct constraint between these two appointments
                            # If both are scheduled, their gap must be <= MAX_GAP_BETWEEN_STREETS_MINUTES
                            # OR one must come before the other

                            # Both scheduled
                            both_scheduled = model.NewBoolVar(f"both_{id1}_{id2}_scheduled")
                            model.AddBoolAnd([is_scheduled[id1], is_scheduled[id2]]).OnlyEnforceIf(both_scheduled)

                            # id1 before id2
                            id1_before_id2 = model.NewBoolVar(f"{id1}_before_{id2}")
                            model.Add(appointment_vars[id1] + appointment_durations[id1] <= appointment_vars[
                                id2]).OnlyEnforceIf(id1_before_id2)

                            # id2 before id1
                            id2_before_id1 = model.NewBoolVar(f"{id2}_before_{id1}")
                            model.Add(appointment_vars[id2] + appointment_durations[id2] <= appointment_vars[
                                id1]).OnlyEnforceIf(id2_before_id1)

                            # If both are scheduled, one must be before the other
                            model.AddBoolOr([id1_before_id2, id2_before_id1]).OnlyEnforceIf(both_scheduled)

                            # Calculate gap if id1 before id2
                            gap_1_to_2 = model.NewIntVar(0, total_minutes, f"gap_{id1}_to_{id2}")
                            model.Add(gap_1_to_2 == appointment_vars[id2] - (
                                        appointment_vars[id1] + appointment_durations[id1])).OnlyEnforceIf(
                                [both_scheduled, id1_before_id2])

                            # Calculate gap if id2 before id1
                            gap_2_to_1 = model.NewIntVar(0, total_minutes, f"gap_{id2}_to_{id1}")
                            model.Add(gap_2_to_1 == appointment_vars[id1] - (
                                        appointment_vars[id2] + appointment_durations[id2])).OnlyEnforceIf(
                                [both_scheduled, id2_before_id1])

                            # THE KEY CONSTRAINT: prohibit gaps > MAX_GAP_BETWEEN_STREETS_MINUTES
                            model.Add(gap_1_to_2 <= self.MAX_GAP_BETWEEN_STREETS_MINUTES).OnlyEnforceIf(
                                [both_scheduled, id1_before_id2])
                            model.Add(gap_2_to_1 <= self.MAX_GAP_BETWEEN_STREETS_MINUTES).OnlyEnforceIf(
                                [both_scheduled, id2_before_id1])

        # Add objective: maximize the number of scheduled appointments
        objective_terms = []

        # Prioritize high priority appointments
        for app_id, is_sched in is_scheduled.items():
            app = next((a for a in appointments if a.id == app_id), None)
            if app:
                # Weight based on priority
                priority_weight = 1
                if app.priority == Priority.HIGH:
                    priority_weight = 10
                elif app.priority == Priority.MEDIUM:
                    priority_weight = 5

                objective_terms.append(is_sched * priority_weight)

        # Small bonus for scheduling more appointments on days where streets are scheduled
        if streets_appointments and zoom_appointments:
            has_streets_var = model.NewBoolVar("has_streets_on_day")
            model.Add(sum(is_scheduled[app_id] for app_id in streets_appointments) >= 1).OnlyEnforceIf(has_streets_var)
            model.Add(sum(is_scheduled[app_id] for app_id in streets_appointments) == 0).OnlyEnforceIf(
                has_streets_var.Not())

            # We can't directly multiply boolean variables, so create combined variables for each zoom session
            for app_id in zoom_appointments:
                bonus_var = model.NewBoolVar(f"bonus_for_{app_id}")
                model.AddBoolAnd([has_streets_var, is_scheduled[app_id]]).OnlyEnforceIf(bonus_var)
                model.AddBoolOr([has_streets_var.Not(), is_scheduled[app_id].Not()]).OnlyEnforceIf(bonus_var.Not())

                # Add a bonus for this zoom session if streets are scheduled on the same day
                objective_terms.append(bonus_var * 2)

        model.Maximize(sum(objective_terms))

        # Create and configure the solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0  # Time limit of 60 seconds

        # Use a more aggressive search strategy for better solutions
        solver.log_search_progress = True

        try:
            # Solve the model
            status = solver.Solve(model)
        except Exception as e:
            logger.error(f"Error solving model for {date}: {e}")
            return []

        # Process the solution
        scheduled_appointments = []

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info(f"Solution found for {date} with status: {solver.StatusName(status)}")

            # Track which clients have appointments scheduled
            scheduled_clients = set()

            # Process each appointment
            for app_id, start_var in appointment_vars.items():
                # Get start time in minutes
                start_minute = solver.Value(start_var)

                # Skip if not scheduled
                if start_minute < 0:
                    logger.debug(f"Appointment {app_id} not scheduled")
                    continue

                # Get client ID
                client_id = appointment_client_ids[app_id]

                # Skip if client already has an appointment today (safety check)
                if client_id in scheduled_clients:
                    logger.warning(f"Client {client_id} already has an appointment on {date}, skipping {app_id}")
                    continue

                # Get appointment type
                app_type = appointment_types[app_id]

                # Calculate actual start and end times
                app_start_time = day_start + datetime.timedelta(minutes=start_minute)
                app_end_time = app_start_time + datetime.timedelta(minutes=appointment_durations[app_id])

                # Create the scheduled appointment
                scheduled_app = ScheduledAppointment(
                    appointment_id=app_id,
                    appointment_type=app_type,
                    duration_minutes=appointment_durations[app_id],
                    start_time=app_start_time,
                    end_time=app_end_time
                )

                scheduled_appointments.append(scheduled_app)
                scheduled_clients.add(client_id)

                logger.info(
                    f"Scheduled: {app_id} ({app_type.value}) at {app_start_time.strftime('%Y-%m-%d %H:%M')} for {appointment_durations[app_id]} minutes")

            # Sort appointments by start time
            scheduled_appointments.sort(key=lambda x: x.start_time)

            # Validate the solution
            self._validate_solution(scheduled_appointments, date)
        else:
            status_name = solver.StatusName(status)
            logger.warning(f"No solution found for {date}. Status: {status_name}")

        return scheduled_appointments

    def _validate_solution(self, scheduled_appointments: List[ScheduledAppointment], date: datetime.date) -> None:
        """Validate that all constraints are met in the solution."""
        if not scheduled_appointments:
            return

        # Check one appointment per client
        clients_scheduled = {}
        for app in scheduled_appointments:
            client_id = app.appointment_id
            if client_id in clients_scheduled:
                logger.error(f"CONSTRAINT VIOLATION: Client {client_id} has multiple appointments on {date}")
            clients_scheduled[client_id] = app

        # Sort appointments by start time
        scheduled_appointments.sort(key=lambda x: x.start_time)

        # Check for minimum breaks between appointments
        for i in range(len(scheduled_appointments) - 1):
            current_app = scheduled_appointments[i]
            next_app = scheduled_appointments[i + 1]

            # Calculate break duration
            break_minutes = (next_app.start_time - current_app.end_time).total_seconds() / 60

            # Determine required minimum break
            min_break = self.MIN_BREAK_MINUTES
            if ((current_app.appointment_type.is_zoom_type and next_app.appointment_type.is_streets_type) or
                    (current_app.appointment_type.is_streets_type and next_app.appointment_type.is_zoom_type)):
                min_break = self.MIN_BREAK_BETWEEN_TYPES_MINUTES

            if break_minutes < min_break:
                logger.error(
                    f"CONSTRAINT VIOLATION: Break between {current_app.appointment_id} and {next_app.appointment_id} is {break_minutes} minutes, less than required {min_break} minutes")

        # Check streets-specific constraints
        streets_apps = [app for app in scheduled_appointments if app.appointment_type.is_streets_type]

        # Check minimum streets sessions
        if 0 < len(streets_apps) < self.MIN_STREETS_SESSIONS_PER_DAY:
            logger.error(
                f"CONSTRAINT VIOLATION: Only {len(streets_apps)} streets sessions on {date}, minimum is {self.MIN_STREETS_SESSIONS_PER_DAY}")

        # Check maximum streets time
        streets_minutes = sum(app.duration_minutes for app in streets_apps)
        if streets_minutes > self.MAX_STREETS_MINUTES_PER_DAY:
            logger.error(
                f"CONSTRAINT VIOLATION: Total streets minutes is {streets_minutes}, exceeding maximum {self.MAX_STREETS_MINUTES_PER_DAY}")

        # Check maximum gap between streets sessions
        if len(streets_apps) >= 2:
            streets_apps.sort(key=lambda x: x.start_time)
            for i in range(len(streets_apps) - 1):
                gap_minutes = (streets_apps[i + 1].start_time - streets_apps[i].end_time).total_seconds() / 60
                if gap_minutes > self.MAX_GAP_BETWEEN_STREETS_MINUTES:
                    logger.error(
                        f"CONSTRAINT VIOLATION: Gap between streets sessions {streets_apps[i].appointment_id} and {streets_apps[i + 1].appointment_id} is {gap_minutes} minutes, exceeding maximum {self.MAX_GAP_BETWEEN_STREETS_MINUTES} minutes")

    def export_to_json(self, output_path: str) -> None:
        """Export scheduled appointments to JSON."""
        output = {
            "scheduled_appointments": [
                appointment.to_dict()
                for appointment in self.scheduled_appointments
            ]
        }

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Exported schedule to {output_path}")


def generate_html_output(scheduled_appointments: List[ScheduledAppointment], output_path: str) -> None:
    """Generate an HTML visualization of the scheduled appointments."""
    logger.info(f"Generating HTML visualization at {output_path}")

    # Group appointments by day
    appointments_by_day = {}
    for appointment in scheduled_appointments:
        day = appointment.start_time.date().isoformat()
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appointment)

    # Sort days
    days = sorted(appointments_by_day.keys())

    # Count appointment types
    streets_count = sum(1 for app in scheduled_appointments if app.appointment_type.is_streets_type)
    zoom_count = sum(1 for app in scheduled_appointments if app.appointment_type.is_zoom_type)

    # Generate HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Appointment Schedule Visualization</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .summary {
                background-color: #f8f9fa;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
            }
            .day-container {
                margin-bottom: 30px;
            }
            .day-header {
                background-color: #f0f0f0;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            .timeline {
                position: relative;
                margin-top: 20px;
                border-left: 2px solid #ccc;
                padding-left: 20px;
                margin-left: 10px;
            }
            .appointment {
                position: relative;
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .streets, .trial_streets {
                background-color: #d4edda;
                border-left: 4px solid #28a745;
            }
            .zoom, .trial_zoom {
                background-color: #cce5ff;
                border-left: 4px solid #007bff;
            }
            .appointment-time {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .appointment-details {
                font-size: 14px;
            }
            .legend {
                display: flex;
                justify-content: center;
                margin-bottom: 20px;
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin: 0 10px;
            }
            .legend-color {
                width: 20px;
                height: 20px;
                margin-right: 5px;
                border-radius: 3px;
            }
            .streets-color {
                background-color: #d4edda;
                border-left: 4px solid #28a745;
            }
            .zoom-color {
                background-color: #cce5ff;
                border-left: 4px solid #007bff;
            }
        </style>
    </head>
    <body>
        <h1>Appointment Schedule Visualization</h1>

        <div class="summary">
            <h2>Schedule Summary</h2>
            <p>Total appointments scheduled: <strong>""" + str(len(scheduled_appointments)) + """</strong></p>
            <p>Streets sessions: <strong>""" + str(streets_count) + """</strong></p>
            <p>Zoom sessions: <strong>""" + str(zoom_count) + """</strong></p>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color streets-color"></div>
                <span>Streets Sessions</span>
            </div>
            <div class="legend-item">
                <div class="legend-color zoom-color"></div>
                <span>Zoom Sessions</span>
            </div>
        </div>
    """

    # Add each day's appointments
    for day in days:
        day_appointments = appointments_by_day[day]
        day_date = datetime.datetime.fromisoformat(day).strftime("%A, %B %d, %Y")

        html_content += f"""
        <div class="day-container">
            <div class="day-header">{day_date}</div>
            <div class="timeline">
        """

        # Sort appointments by start time
        day_appointments.sort(key=lambda x: x.start_time)

        for appointment in day_appointments:
            app_type = appointment.appointment_type.value
            start_time = appointment.start_time.strftime("%H:%M")
            end_time = appointment.end_time.strftime("%H:%M")
            duration = appointment.duration_minutes

            html_content += f"""
                <div class="appointment {app_type}">
                    <div class="appointment-time">{start_time} - {end_time}</div>
                    <div class="appointment-details">
                        <strong>ID:</strong> {appointment.appointment_id}<br>
                        <strong>Type:</strong> {app_type}<br>
                        <strong>Duration:</strong> {duration} minutes
                    </div>
                </div>
            """

        html_content += """
            </div>
        </div>
        """

    html_content += """
    </body>
    </html>
    """

    # Write to file
    with open(output_path, 'w') as f:
        f.write(html_content)

    logger.info(f"HTML visualization generated at {output_path}")


def print_schedule_summary(scheduled_appointments: List[ScheduledAppointment]) -> None:
    """Print a summary of the schedule to stdout."""
    print("\n=== APPOINTMENT SCHEDULE SUMMARY ===")
    print(f"Total scheduled appointments: {len(scheduled_appointments)}")

    # Count by type
    streets_count = sum(1 for app in scheduled_appointments if app.appointment_type.is_streets_type)
    zoom_count = sum(1 for app in scheduled_appointments if app.appointment_type.is_zoom_type)
    print(f"Streets sessions: {streets_count}")
    print(f"Zoom sessions: {zoom_count}")

    # Group by day for better readability
    appointments_by_day = {}
    for appointment in scheduled_appointments:
        day = appointment.start_time.strftime("%Y-%m-%d")
        if day not in appointments_by_day:
            appointments_by_day[day] = []
        appointments_by_day[day].append(appointment)

    # Print by day
    for day, day_appointments in sorted(appointments_by_day.items()):
        streets_day_count = sum(1 for app in day_appointments if app.appointment_type.is_streets_type)
        zoom_day_count = sum(1 for app in day_appointments if app.appointment_type.is_zoom_type)

        print(
            f"\n--- {day} ({len(day_appointments)} appointments: {streets_day_count} streets, {zoom_day_count} zoom) ---")

        # Sort by start time
        day_appointments.sort(key=lambda x: x.start_time)

        for app in day_appointments:
            start_time = app.start_time.strftime("%H:%M")
            end_time = app.end_time.strftime("%H:%M")
            print(
                f"  {start_time} - {end_time}: Client {app.appointment_id} ({app.appointment_type.value}, {app.duration_minutes} min)")


def parse_input_json(file_path: str) -> Tuple[datetime.date, List[Appointment]]:
    """Parse input JSON file containing appointment data."""
    logger.info(f"Parsing input file: {file_path}")

    with open(file_path, 'r') as f:
        data = json.load(f)

    start_date = datetime.date.fromisoformat(data.get("start_date"))
    appointments = []

    for appointment_data in data.get("appointments", []):
        try:
            appointment = Appointment.from_dict(appointment_data)
            appointments.append(appointment)
        except Exception as e:
            logger.error(f"Error parsing appointment: {e}")

    # Log appointment types summary
    streets_count = sum(1 for app in appointments if app.appointment_type.is_streets_type)
    zoom_count = sum(1 for app in appointments if app.appointment_type.is_zoom_type)
    logger.info(f"Parsed {len(appointments)} appointments: {streets_count} streets and {zoom_count} zoom sessions")

    return start_date, appointments


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Improved Appointment Scheduler using Google's CP-SAT solver")
    parser.add_argument('input_file', help='Path to the input JSON file')
    parser.add_argument('--output-json', default='scheduled_appointments.json', help='Path for the output JSON file')
    parser.add_argument('--output-html', default='schedule_visualization.html',
                        help='Path for the output HTML visualization')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Set the logging level')

    args = parser.parse_args()

    # Set logging level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)

    try:
        # Parse the input file
        start_date, appointments = parse_input_json(args.input_file)

        # Create the scheduler
        scheduler = AppointmentScheduler(start_date)

        # Add appointments to be scheduled
        for appointment in appointments:
            scheduler.add_appointment(appointment)

        # Schedule the appointments
        scheduled_appointments = scheduler.schedule()

        # Print schedule summary to stdout
        print_schedule_summary(scheduled_appointments)

        # Export to JSON
        scheduler.export_to_json(args.output_json)

        # Generate HTML visualization
        generate_html_output(scheduled_appointments, args.output_html)

        logger.info("Scheduling process completed successfully")

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
