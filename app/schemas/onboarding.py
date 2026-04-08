from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

DEFAULT_STEPS = [
    {"key": "document_collection", "label": "Document Collection"},
    {"key": "background_check",    "label": "Background Verification"},
    {"key": "system_access",       "label": "System Access Setup"},
    {"key": "equipment_handover",  "label": "Equipment Handover"},
    {"key": "orientation",         "label": "Company Orientation"},
    {"key": "policy_sign",         "label": "Policy & NDA Sign-off"},
    {"key": "team_intro",          "label": "Team Introduction"},
    {"key": "training",            "label": "Initial Training"},
]


class OnboardingStep(BaseModel):
    key: str
    label: str
    completed: bool = False
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class OnboardingStepUpdate(BaseModel):
    completed: bool
    notes: Optional[str] = None


class OnboardingOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_eid: str
    department: str
    steps: List[OnboardingStep]
    progress: int
    created_at: datetime
    updated_at: datetime
