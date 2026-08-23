from dataclasses import dataclass


@dataclass
class ScheduledJob:

    id: str = ""
    customer_id: str = ""
    site_id: str = ""
    quote_id: str = ""
    job_card_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "Scheduled"
    start_date: str = ""
    end_date: str = ""
    assigned_to: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""
