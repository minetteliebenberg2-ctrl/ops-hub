# ==========================================================
# FC Hub - Calendar Services
# ----------------------------------------------------------
# Purpose:
# Job scheduling, project timeline management, team coordination.
#
# Author: Minette & James
# Version: 1.0
# ==========================================================

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict
from enum import Enum


class JobStatus(Enum):
    """Job/project status"""
    QUOTED = "Quoted"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    ON_HOLD = "On Hold"
    CANCELLED = "Cancelled"


class JobPhase(Enum):
    """Project phase"""
    BEFORE = "Before"
    DURING = "During"
    AFTER = "After"


@dataclass
class JobTask:
    """Individual task within a job"""

    task_id: str
    job_id: str
    title: str
    description: str = ""
    assigned_to: str = ""
    start_date: str = ""
    due_date: str = ""
    status: str = "Pending"
    priority: str = "Normal"  # Low, Normal, High, Critical
    notes: str = ""


@dataclass
class Job:
    """Job/project record"""

    job_id: str
    customer_name: str = ""
    customer_id: str = ""
    title: str = ""
    description: str = ""
    status: str = JobStatus.QUOTED.value
    phase: str = JobPhase.BEFORE.value

    # Dates
    quote_date: str = ""
    start_date: str = ""
    completion_date: str = ""

    # Team
    assigned_to: str = ""
    team_members: List[str] = field(default_factory=list)

    # Financial
    quoted_amount: float = 0.0
    actual_cost: float = 0.0

    # Tasks
    tasks: List[JobTask] = field(default_factory=list)

    # Gallery
    gallery_phases: Dict[str, List[str]] = field(default_factory=lambda: {
        "Before": [],
        "During": [],
        "After": [],
    })

    # Notes
    notes: str = ""
    created_date: str = ""
    updated_date: str = ""

    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat(timespec="seconds")
        if not self.updated_date:
            self.updated_date = datetime.now().isoformat(timespec="seconds")


@dataclass
class TeamMember:
    """Team member availability and skills"""

    member_id: str
    name: str
    email: str = ""
    phone: str = ""
    skills: List[str] = field(default_factory=list)
    availability: Dict[str, str] = field(default_factory=dict)  # date -> available/busy


class CalendarService:
    """Service for managing jobs and schedules"""

    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.team_members: Dict[str, TeamMember] = {}
        self.next_job_id = 1

    # --------------------------------------------------

    def create_job(self, customer_name: str, title: str) -> Job:
        """Create a new job"""
        job_id = f"JOB-{self.next_job_id:04d}"
        self.next_job_id += 1

        job = Job(
            job_id=job_id,
            customer_name=customer_name,
            title=title,
        )

        self.jobs[job_id] = job
        return job

    # --------------------------------------------------

    def get_job(self, job_id: str) -> Job:
        """Retrieve a job by ID"""
        return self.jobs.get(job_id)

    # --------------------------------------------------

    def get_jobs_by_status(self, status: str) -> List[Job]:
        """Get all jobs with a specific status"""
        return [j for j in self.jobs.values() if j.status == status]

    # --------------------------------------------------

    def get_jobs_by_date_range(self, start_date: str, end_date: str) -> List[Job]:
        """Get jobs scheduled between dates"""
        return [
            j for j in self.jobs.values()
            if j.start_date and start_date <= j.start_date <= end_date
        ]

    # --------------------------------------------------

    def update_job_status(self, job_id: str, status: str):
        """Update job status"""
        job = self.get_job(job_id)
        if job:
            job.status = status
            job.updated_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def update_job_phase(self, job_id: str, phase: str):
        """Update job phase (Before/During/After)"""
        job = self.get_job(job_id)
        if job:
            job.phase = phase
            job.updated_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def add_task_to_job(self, job_id: str, task: JobTask):
        """Add a task to a job"""
        job = self.get_job(job_id)
        if job:
            job.tasks.append(task)
            job.updated_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def add_gallery_image(self, job_id: str, phase: str, image_path: str):
        """Add image to job gallery for a specific phase"""
        job = self.get_job(job_id)
        if job and phase in job.gallery_phases:
            job.gallery_phases[phase].append(image_path)
            job.updated_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def register_team_member(self, member: TeamMember):
        """Register a team member"""
        self.team_members[member.member_id] = member

    # --------------------------------------------------

    def assign_job(self, job_id: str, team_member_id: str):
        """Assign a job to a team member"""
        job = self.get_job(job_id)
        if job and team_member_id in self.team_members:
            job.assigned_to = team_member_id
            if team_member_id not in job.team_members:
                job.team_members.append(team_member_id)
            job.updated_date = datetime.now().isoformat(timespec="seconds")

    # --------------------------------------------------

    def get_calendar_summary(self, month: str = None) -> Dict:
        """Get summary of jobs for a month"""
        if not month:
            month = datetime.now().strftime("%Y-%m")

        summary = {
            "month": month,
            "total_jobs": 0,
            "by_status": {},
            "by_phase": {},
            "upcoming": [],
            "in_progress": [],
            "overdue": [],
            "total_quoted": 0.0,
            "total_actual": 0.0,
        }

        for job in self.jobs.values():
            if job.start_date and job.start_date.startswith(month):
                summary["total_jobs"] += 1
                summary["by_status"][job.status] = summary["by_status"].get(job.status, 0) + 1
                summary["by_phase"][job.phase] = summary["by_phase"].get(job.phase, 0) + 1

                if job.status == JobStatus.IN_PROGRESS.value:
                    summary["in_progress"].append(job)
                elif job.status == JobStatus.SCHEDULED.value:
                    summary["upcoming"].append(job)

                summary["total_quoted"] += job.quoted_amount
                summary["total_actual"] += job.actual_cost

        return summary
