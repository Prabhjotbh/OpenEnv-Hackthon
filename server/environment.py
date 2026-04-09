import uuid
import copy
from typing import Optional
from models import (
    ProcureObservation, ProcureState, SupplierVisible,
    QueryAction, RequestDocAction, OfferAction, AcceptAction, RejectAction
)
from tasks import TASKS


class ProcureEnvironment:
    """
    Core environment logic. One instance per WebSocket session.
    All state is stored on self.
    """

    def __init__(self, task_id: str = "task1_easy"):
        self.task_id = task_id
        self._task = TASKS[task_id]
        self._episode_id: Optional[str] = None
        self._suppliers: list[dict] = []
        self._rejected_ids: set[int] = set()
        self._accepted_id: Optional[int] = None
        self._revealed: dict[str, dict] = {}
        self._best_offers: dict[str, float] = {}
        self._step_count: int = 0
        self._cumulative_reward: float = 0.0
        self._done: bool = False
        self._deceptive_trap_triggered: dict[int, bool] = {}

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def reset(self) -> ProcureObservation:
        self._episode_id = str(uuid.uuid4())[:8]
        self._suppliers = copy.deepcopy(self._task["suppliers"])
        self._rejected_ids = set()
        self._accepted_id = None
        self._revealed = {str(s["id"]): {} for s in self._suppliers}
        self._best_offers = {str(s["id"]): s["quoted_price"] for s in self._suppliers}
        self._step_count = 0
        self._cumulative_reward = 0.0
        self._done = False
        self._deceptive_trap_triggered = {s["id"]: False for s in self._suppliers}

        msg = (
            f"New procurement task loaded: {self._task['rfq']['item']}. "
            f"Quantity: {self._task['rfq']['quantity']} units. "
            f"Budget: ₹{self._task['rfq']['budget']:,.0f}. "
            f"Deadline: {self._task['rfq']['deadline_days']} days. "
            f"Required certifications: {self._task['rfq']['required_certs'] or 'None'}. "
            f"{len(self._suppliers)} suppliers available. "
            f"You have {self._task['max_steps']} steps. "
            f"Use query, request_doc, offer, accept, or reject actions."
        )
        return self._build_observation(reward=0.0, message=msg)

    def step(self, action: dict) -> ProcureObservation:
        if self._done:
            return self._build_observation(reward=0.0, message="Episode already done. Call reset().")

        self._step_count += 1
        action_type = action.get("action")
        reward = 0.0
        message = ""

        if action_type == "query":
            reward, message = self._handle_query(action)
        elif action_type == "request_doc":
            reward, message = self._handle_request_doc(action)
        elif action_type == "offer":
            reward, message = self._handle_offer(action)
        elif action_type == "accept":
            reward, message = self._handle_accept(action)
        elif action_type == "reject":
            reward, message = self._handle_reject(action)
        else:
            message = f"Unknown action '{action_type}'. Valid: query, request_doc, offer, accept, reject."
            reward = -0.02

        steps_remaining = self._task["max_steps"] - self._step_count
        if steps_remaining <= 0 and not self._done:
            self._done = True
            message += " TIMEOUT: Maximum steps reached without completing procurement."

        self._cumulative_reward += reward
        return self._build_observation(reward=reward, message=message)

    @property
    def state(self) -> ProcureState:
        return ProcureState(
            task_id=self.task_id,
            episode_id=self._episode_id or "",
            step_count=self._step_count,
            done=self._done,
            cumulative_reward=self._cumulative_reward,
            accepted_supplier_id=self._accepted_id,
            suppliers_hidden=self._suppliers
        )

    # ------------------------------------------------------------------ #
    #  Action Handlers                                                     #
    # ------------------------------------------------------------------ #

    def _handle_query(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        field = action.get("field")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"Supplier {sid} has been rejected already."

        field_map = {
            "lead_time": ("lead_time_days", "lead time"),
            "moq": ("moq", "minimum order quantity"),
            "reliability": ("reliability", "reliability score"),
        }
        if field not in field_map:
            return -0.01, f"Unknown field '{field}'. Valid: lead_time, moq, reliability."

        internal_key, display = field_map[field]
        already_known = field in self._revealed[str(sid)]
        value = supplier[internal_key]
        self._revealed[str(sid)][field] = value

        if already_known:
            return 0.0, f"Supplier {supplier['name']}: {display} = {value} (already known)."
        else:
            return 0.01, f"Supplier {supplier['name']}: {display} = {value}."

    def _handle_request_doc(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        doc_type = action.get("doc_type")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"Supplier {sid} has been rejected already."

        doc_map = {
            "quality_report": ("quality_score", "quality score"),
            "certifications": ("certifications", "certifications"),
            "financial_stability": ("reliability", "financial stability / reliability"),
        }
        if doc_type not in doc_map:
            return -0.01, f"Unknown doc_type '{doc_type}'."

        internal_key, display = doc_map[doc_type]
        already_known = doc_type in self._revealed[str(sid)]
        value = supplier[internal_key]
        self._revealed[str(sid)][doc_type] = value

        if already_known:
            return 0.0, f"Supplier {supplier['name']} {display}: {value} (already known)."

        extra_msg = ""
        reward = 0.03
        if doc_type == "quality_report" and isinstance(value, float) and value < 0.6:
            extra_msg = " WARNING: Quality score below acceptable threshold (0.60)."
            reward = 0.05
        if doc_type == "certifications":
            required = self._task["rfq"]["required_certs"]
            missing = [c for c in required if c not in value]
            if missing:
                extra_msg = f" WARNING: Missing required certifications: {missing}."
                reward = 0.05

        return reward, f"Supplier {supplier['name']} {display}: {value}.{extra_msg}"

    def _handle_offer(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        offered_price = action.get("price")
        quantity = action.get("quantity")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"Supplier {sid} has been rejected already."
        if sid == self._accepted_id:
            return -0.01, f"Supplier {sid} already accepted."

        min_price = supplier["min_price"]
        behavior = supplier["behavior"]
        current_price = self._best_offers[str(sid)]

        if offered_price >= current_price:
            return -0.01, (
                f"Supplier {supplier['name']} noted your offer of ₹{offered_price}/unit "
                f"but their current price is already ₹{current_price}/unit. "
                f"Offer at or below current price to negotiate."
            )

        if behavior == "deceptive":
            self._best_offers[str(sid)] = offered_price
            self._deceptive_trap_triggered[sid] = True
            return 0.04, (
                f"Supplier {supplier['name']} accepted your offer of ₹{offered_price}/unit. "
                f"Confirm with accept action to finalize."
            )

        if offered_price < min_price:
            self._best_offers[str(sid)] = min_price
            improvement = (current_price - min_price) / supplier["quoted_price"]
            reward = improvement * 0.3
            return reward, (
                f"Supplier {supplier['name']} cannot go below ₹{min_price}/unit. "
                f"They have countered at ₹{min_price}/unit."
            )

        if behavior == "flexible":
            self._best_offers[str(sid)] = offered_price
            improvement = (current_price - offered_price) / supplier["quoted_price"]
            reward = improvement * 0.5
            return reward, (
                f"Supplier {supplier['name']} accepted your offer of ₹{offered_price}/unit. "
                f"Price locked in. Confirm with accept action."
            )

        if behavior == "firm":
            counter = round((offered_price + min_price) / 2, 2)
            self._best_offers[str(sid)] = counter
            improvement = (current_price - counter) / supplier["quoted_price"]
            reward = improvement * 0.3
            return reward, (
                f"Supplier {supplier['name']} countered at ₹{counter}/unit "
                f"(their best offer)."
            )

        return 0.0, f"Offer to supplier {sid} processed."

    def _handle_accept(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"Cannot accept rejected supplier {sid}."

        if supplier["behavior"] == "deceptive" and self._deceptive_trap_triggered.get(sid):
            revised_price = round(self._best_offers[str(sid)] * 1.20, 2)
            self._best_offers[str(sid)] = revised_price
            self._done = True
            self._accepted_id = sid
            final_score = self._compute_final_score(sid, was_deceived=True)
            self._cumulative_reward += final_score
            return final_score, (
                f"DECEPTION: Supplier {supplier['name']} has revised their price to "
                f"₹{revised_price}/unit (+20%) upon finalization. "
                f"You have been locked in. Final score: {final_score:.2f}. "
                f"Hint: Always verify supplier reliability and certifications before accepting."
            )

        self._accepted_id = sid
        self._done = True
        final_score = self._compute_final_score(sid, was_deceived=False)
        price = self._best_offers[str(sid)]
        total_cost = price * self._task["rfq"]["quantity"]

        required_certs = self._task["rfq"]["required_certs"]
        supplier_certs = supplier["certifications"]
        missing_certs = [c for c in required_certs if c not in supplier_certs]
        cert_msg = ""
        if missing_certs:
            cert_msg = f" WARNING: Missing required certs {missing_certs} -- compliance penalty applied."

        return final_score, (
            f"Accepted Supplier {supplier['name']} at ₹{price}/unit. "
            f"Total cost: ₹{total_cost:,.0f} (budget: ₹{self._task['rfq']['budget']:,.0f}).{cert_msg} "
            f"Final score: {final_score:.2f}."
        )

    def _handle_reject(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier {sid} not found."
        if sid in self._rejected_ids:
            return 0.0, f"Supplier {sid} already rejected."

        self._rejected_ids.add(sid)

        all_ids = {s["id"] for s in self._suppliers}
        if self._rejected_ids == all_ids:
            self._done = True
            return -0.5, f"Rejected Supplier {supplier['name']}. All suppliers rejected -- procurement failed."

        return 0.0, f"Rejected Supplier {supplier['name']}. They have been removed from consideration."

    # ------------------------------------------------------------------ #
    #  Grader / Final Score                                               #
    # ------------------------------------------------------------------ #

    def _compute_final_score(self, accepted_sid: int, was_deceived: bool) -> float:
        """
        Returns a score 0.0-1.0 based on:
        - Cost efficiency (40%)
        - Certification compliance (30%)
        - Quality check performed (20%)
        - Due diligence (10%)
        """
        supplier = self._get_supplier(accepted_sid)
        rfq = self._task["rfq"]
        revealed = self._revealed[str(accepted_sid)]

        # 1. Cost efficiency (0.0-0.4)
        final_price = self._best_offers[str(accepted_sid)]
        total_cost = final_price * rfq["quantity"]
        budget = rfq["budget"]

        if total_cost > budget:
            cost_score = 0.0
        else:
            valid_suppliers = [
                s for s in self._suppliers
                if all(c in s["certifications"] for c in rfq["required_certs"])
                and s["quality_score"] >= 0.6
            ]
            if valid_suppliers:
                best_possible = min(s["min_price"] for s in valid_suppliers) * rfq["quantity"]
                worst_reasonable = max(s["quoted_price"] for s in valid_suppliers) * rfq["quantity"]
                cost_score = 0.4 * max(0.0, (worst_reasonable - total_cost) / max(worst_reasonable - best_possible, 1))
            else:
                cost_score = 0.2

        # 2. Certification compliance (0.0-0.3)
        required_certs = rfq["required_certs"]
        if not required_certs:
            cert_score = 0.3
        else:
            supplier_certs = supplier["certifications"]
            certs_met = sum(1 for c in required_certs if c in supplier_certs)
            cert_score = 0.3 * (certs_met / len(required_certs))

        # 3. Quality check (0.0-0.2)
        if "quality_report" in revealed:
            quality_score_val = supplier["quality_score"]
            quality_score = 0.2 if quality_score_val >= 0.6 else 0.05
        else:
            quality_score = 0.0

        # 4. Due diligence (0.0-0.1)
        checks = len([k for k in revealed if k in ("lead_time", "moq", "reliability", "certifications")])
        diligence_score = min(0.1, checks * 0.04)

        if was_deceived:
            total = (cost_score + cert_score + quality_score + diligence_score) * 0.4
        else:
            total = cost_score + cert_score + quality_score + diligence_score

        return round(min(0.999, max(0.001, total)), 3)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _get_supplier(self, sid: int) -> Optional[dict]:
        for s in self._suppliers:
            if s["id"] == sid:
                return s
        return None

    def _build_observation(self, reward: float, message: str) -> ProcureObservation:
        visible = []
        for s in self._suppliers:
            status = "active"
            if s["id"] in self._rejected_ids:
                status = "rejected"
            elif s["id"] == self._accepted_id:
                status = "accepted"
            visible.append(SupplierVisible(
                id=s["id"],
                name=s["name"],
                quoted_price=s["quoted_price"],
                item_category=s["item_category"],
                status=status
            ))

        enriched = self._enrich_message(message)

        return ProcureObservation(
            rfq=self._task["rfq"],
            suppliers=visible,
            revealed_info=self._revealed,
            current_best_offers=self._best_offers,
            step_count=self._step_count,
            steps_remaining=self._task["max_steps"] - self._step_count,
            done=self._done,
            reward=reward,
            cumulative_reward=self._cumulative_reward,
            accepted_supplier_id=self._accepted_id,
            message=enriched
        )

    def _enrich_message(self, base_message: str) -> str:
        steps_remaining = self._task["max_steps"] - self._step_count
        if self._done or steps_remaining <= 0:
            return base_message

        required_certs = self._task["rfq"]["required_certs"]
        parts = [base_message]
        parts.append(f"Steps remaining: {steps_remaining}/{self._task['max_steps']}.")

        # Flag active suppliers with unchecked certifications
        if required_certs:
            unchecked = []
            for s in self._suppliers:
                sid = s["id"]
                if sid in self._rejected_ids or sid == self._accepted_id:
                    continue
                if "certifications" not in self._revealed.get(str(sid), {}):
                    unchecked.append(s["name"])
            if unchecked:
                parts.append(
                    f"Cert check needed for: {', '.join(unchecked)}. "
                    f"Required: {required_certs}."
                )

        # Flag active suppliers without quality reports
        no_quality = []
        for s in self._suppliers:
            sid = s["id"]
            if sid in self._rejected_ids or sid == self._accepted_id:
                continue
            if "quality_report" not in self._revealed.get(str(sid), {}):
                no_quality.append(s["name"])
        if no_quality:
            parts.append(
                f"Quality report not yet requested for: {', '.join(no_quality)}."
            )

        # Summarize revealed info for active suppliers
        revealed_summaries = []
        for s in self._suppliers:
            sid = s["id"]
            if sid in self._rejected_ids:
                continue
            revealed = self._revealed.get(str(sid), {})
            if revealed:
                kvs = [f"{k}={v}" for k, v in revealed.items()]
                revealed_summaries.append(f"{s['name']}: {', '.join(kvs)}")
        if revealed_summaries:
            parts.append(f"Known info: {'; '.join(revealed_summaries)}.")

        return " | ".join(parts)
