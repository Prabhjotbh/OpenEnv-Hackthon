from pydantic import BaseModel
from typing import Optional, Literal, Any


# --- Actions ---

class QueryAction(BaseModel):
    action: Literal["query"] = "query"
    supplier_id: int
    field: Literal["lead_time", "moq", "reliability"]


class RequestDocAction(BaseModel):
    action: Literal["request_doc"] = "request_doc"
    supplier_id: int
    doc_type: Literal["quality_report", "certifications", "financial_stability"]


class OfferAction(BaseModel):
    action: Literal["offer"] = "offer"
    supplier_id: int
    price: float
    quantity: int


class AcceptAction(BaseModel):
    action: Literal["accept"] = "accept"
    supplier_id: int


class RejectAction(BaseModel):
    action: Literal["reject"] = "reject"
    supplier_id: int


ProcureAction = QueryAction | RequestDocAction | OfferAction | AcceptAction | RejectAction


# --- Observation (what the agent sees each step) ---

class SupplierVisible(BaseModel):
    id: int
    name: str
    quoted_price: float
    item_category: str
    status: str  # "active" | "rejected" | "accepted"


class ProcureObservation(BaseModel):
    rfq: dict
    suppliers: list[SupplierVisible]
    revealed_info: dict[str, dict]
    current_best_offers: dict[str, float]
    step_count: int
    steps_remaining: int
    done: bool
    reward: float
    cumulative_reward: float
    accepted_supplier_id: Optional[int]
    message: str


# --- State (internal, returned by /state endpoint) ---

class ProcureState(BaseModel):
    task_id: str
    episode_id: str
    step_count: int
    done: bool
    cumulative_reward: float
    accepted_supplier_id: Optional[int]
    suppliers_hidden: list[dict]
