import uuid
import copy
from typing import Optional
from models import (
    ProcureObservation, ProcureState, SupplierVisible,
    QueryAction, RequestDocAction, OfferAction, AcceptAction, RejectAction
)
from tasks import TASKS

# --- Reward weights for the terminal score breakdown ---
COST_EFFICIENCY_WEIGHT = 0.40
CERT_COMPLIANCE_WEIGHT = 0.30
QUALITY_CHECK_WEIGHT   = 0.20
DUE_DILIGENCE_WEIGHT   = 0.10

# Deception penalty: accepting a supplier who ran a bait-and-switch multiplies
# the total terminal score by this factor. 0.4 is intentionally harsh -- in real
# procurement, getting locked into a deceptive supplier costs time and money to unwind.
DECEPTION_PENALTY_MULTIPLIER = 0.40

# Quality threshold below which a supplier should be rejected.
# Matches real ISO inspection acceptance criteria (~60% pass rate floor).
QUALITY_THRESHOLD = 0.60

# Score bounds: the OpenEnv validator rejects exactly 0.0 and 1.0.
# Clamp all final scores to this open interval.
SCORE_MIN = 0.001
SCORE_MAX = 0.999

# Per-step reward for revealing new information.
REWARD_QUERY_NEW     = 0.01   # query field not previously known
REWARD_DOC_NEW       = 0.03   # request_doc not previously seen
REWARD_ISSUE_FOUND   = 0.05   # quality < threshold or missing required cert discovered
REWARD_DECEPTIVE_BAIT = 0.04  # deceptive supplier "accepts" during negotiation (bait)


class ProcureEnvironment:
    """
    Core environment logic for one procurement episode.

    One instance per WebSocket session. All mutable state lives on self --
    there is no shared state between sessions. The environment is reset
    explicitly via reset(), not at construction time, so the same instance
    can be reused across episodes (the server currently creates a new instance
    per session, but this pattern supports reuse).

    Episode lifecycle:
      1. reset(task_id) -- loads task, initialises supplier pool, returns obs
      2. step(action)   -- processes one agent action, returns next obs + reward
      3. Repeat until obs.done == True (accept, all-rejected, or step budget exhausted)
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

        rfq = self._task["rfq"]
        supplier_names = ", ".join(s["name"] for s in self._suppliers)
        certs_note = (
            f" Required certifications: {rfq['required_certs']}."
            if rfq["required_certs"] else ""
        )
        msg = (
            f"RFQ: {rfq['item']} -- {rfq['quantity']} units, "
            f"budget ₹{rfq['budget']:,.0f}, deadline {rfq['deadline_days']} days.{certs_note} "
            f"Suppliers: {supplier_names}. "
            f"Step budget: {self._task['max_steps']} steps. "
            f"Verify certifications and quality before accepting."
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
            message += " TIMEOUT: step budget exhausted without completing procurement."

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
            return -0.01, f"Supplier ID {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"{supplier['name']} has already been rejected."

        field_map = {
            "lead_time":   ("lead_time_days", "lead time (days)"),
            "moq":         ("moq",            "minimum order quantity"),
            "reliability": ("reliability",    "reliability score"),
        }
        if field not in field_map:
            return -0.01, f"Unknown field '{field}'. Valid: lead_time, moq, reliability."

        internal_key, display = field_map[field]
        already_known = field in self._revealed[str(sid)]
        value = supplier[internal_key]
        self._revealed[str(sid)][field] = value

        name = supplier["name"]
        if already_known:
            return 0.0, f"{name}: {display} = {value} (already on record)."

        # Add context when the value is decision-relevant
        note = ""
        if field == "lead_time" and self._task["rfq"].get("deadline_days"):
            deadline = self._task["rfq"]["deadline_days"]
            if value > deadline:
                note = f" That exceeds your {deadline}-day deadline -- worth flagging."
        if field == "reliability" and isinstance(value, float) and value < 0.80:
            note = " Reliability below 0.80 -- verify carefully before committing."

        return REWARD_QUERY_NEW, f"{name}: {display} = {value}.{note}"

    def _handle_request_doc(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        doc_type = action.get("doc_type")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier ID {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"{supplier['name']} has already been rejected."

        doc_map = {
            "quality_report":      ("quality_score",  "quality score"),
            "certifications":      ("certifications", "certifications"),
            "financial_stability": ("reliability",    "financial stability / reliability"),
        }
        if doc_type not in doc_map:
            return -0.01, f"Unknown doc_type '{doc_type}'. Valid: quality_report, certifications, financial_stability."

        internal_key, display = doc_map[doc_type]
        already_known = doc_type in self._revealed[str(sid)]
        value = supplier[internal_key]
        self._revealed[str(sid)][doc_type] = value
        name = supplier["name"]

        if already_known:
            return 0.0, f"{name} {display}: {value} (already on record)."

        extra_msg = ""
        reward = REWARD_DOC_NEW

        if doc_type == "quality_report" and isinstance(value, float):
            grade = (
                "Excellent" if value >= 0.85 else
                "Good"      if value >= 0.70 else
                "Acceptable" if value >= QUALITY_THRESHOLD else
                "Below threshold"
            )
            extra_msg = f" ({grade})"
            if value < QUALITY_THRESHOLD:
                extra_msg += f" -- below the {QUALITY_THRESHOLD} floor. Recommend rejecting."
                reward = REWARD_ISSUE_FOUND

        if doc_type == "certifications":
            required = self._task["rfq"]["required_certs"]
            missing = [c for c in required if c not in value]
            if missing:
                extra_msg = f" WARNING: missing required certs: {missing}. This supplier cannot be accepted."
                reward = REWARD_ISSUE_FOUND

        return reward, f"{name} {display}: {value}.{extra_msg}"

    def _handle_offer(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        offered_price = action.get("price")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier ID {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"{supplier['name']} has already been rejected."
        if sid == self._accepted_id:
            return -0.01, f"{supplier['name']} is already accepted."

        name = supplier["name"]
        min_price = supplier["min_price"]
        behavior = supplier["behavior"]
        current_price = self._best_offers[str(sid)]

        if offered_price >= current_price:
            return -0.01, (
                f"{name} noted ₹{offered_price:,.0f}/unit but their current price is "
                f"₹{current_price:,.0f}. Offer below their current price to negotiate."
            )

        if behavior == "deceptive":
            # Deceptive supplier accepts anything during negotiation -- trap springs on accept().
            # Record that the bait was taken so accept() can fire the revision.
            self._best_offers[str(sid)] = offered_price
            self._deceptive_trap_triggered[sid] = True
            return REWARD_DECEPTIVE_BAIT, (
                f"{name} confirmed ₹{offered_price:,.0f}/unit. "
                f"Use accept to finalise -- verify their reliability score first."
            )

        if offered_price < min_price:
            # Offered below floor: supplier counters at their minimum.
            self._best_offers[str(sid)] = min_price
            improvement = (current_price - min_price) / supplier["quoted_price"]
            reward = improvement * 0.3
            return reward, (
                f"{name} cannot go below ₹{min_price:,.0f}/unit -- that's their floor. "
                f"Countered at ₹{min_price:,.0f}."
            )

        if behavior == "flexible":
            self._best_offers[str(sid)] = offered_price
            improvement = (current_price - offered_price) / supplier["quoted_price"]
            reward = improvement * 0.5
            return reward, (
                f"{name} accepted ₹{offered_price:,.0f}/unit. "
                f"Price locked in. Use accept to finalise."
            )

        if behavior == "firm":
            # Firm supplier splits the difference once, then holds.
            counter = round((offered_price + min_price) / 2, 0)
            self._best_offers[str(sid)] = counter
            improvement = (current_price - counter) / supplier["quoted_price"]
            reward = improvement * 0.3
            return reward, (
                f"{name} came down to ₹{counter:,.0f}/unit -- that's their best offer."
            )

        return 0.0, f"Offer to {name} processed."

    def _handle_accept(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier ID {sid} not found."
        if sid in self._rejected_ids:
            return -0.01, f"Cannot accept {supplier['name']} -- already rejected."

        name = supplier["name"]

        # Deception trap: FluidDyn-style supplier agreed during negotiation but springs
        # a price revision on the formal accept call. The agent should have noticed the
        # low reliability score and missing CE cert before reaching this point.
        if supplier["behavior"] == "deceptive" and self._deceptive_trap_triggered.get(sid):
            agreed = self._best_offers[str(sid)]
            revised = round(agreed * 1.20, 0)
            self._best_offers[str(sid)] = revised
            self._done = True
            self._accepted_id = sid
            final_score = self._compute_final_score(sid, was_deceived=True)
            # Note: step() adds the returned reward to cumulative_reward -- do not add here.
            return final_score, (
                f"DECEPTION: {name} has revised their price to ₹{revised:,.0f}/unit "
                f"(+20% from the ₹{agreed:,.0f} agreed during negotiation), "
                f"citing 'raw material cost escalation.' "
                f"Deal locked in at revised price. "
                f"Final score: {final_score:.3f}. "
                f"Hint: low reliability score and missing certifications were warning signs."
            )

        self._accepted_id = sid
        self._done = True
        final_score = self._compute_final_score(sid, was_deceived=False)
        price = self._best_offers[str(sid)]
        total_cost = price * self._task["rfq"]["quantity"]
        budget = self._task["rfq"]["budget"]

        required_certs = self._task["rfq"]["required_certs"]
        supplier_certs = supplier["certifications"]
        missing_certs = [c for c in required_certs if c not in supplier_certs]
        cert_msg = ""
        if missing_certs:
            cert_msg = f" WARNING: missing required certs {missing_certs} -- compliance penalty applied."

        budget_note = (
            f"within budget (saved ₹{budget - total_cost:,.0f})"
            if total_cost <= budget
            else f"OVER BUDGET by ₹{total_cost - budget:,.0f}"
        )
        return final_score, (
            f"Deal closed: {name} at ₹{price:,.0f}/unit. "
            f"Total: ₹{total_cost:,.0f} -- {budget_note}.{cert_msg} "
            f"Final score: {final_score:.3f}."
        )

    def _handle_reject(self, action: dict) -> tuple[float, str]:
        sid = action.get("supplier_id")
        supplier = self._get_supplier(sid)
        if not supplier:
            return -0.01, f"Supplier ID {sid} not found."
        if sid in self._rejected_ids:
            return 0.0, f"{supplier['name']} was already rejected."

        self._rejected_ids.add(sid)
        name = supplier["name"]

        all_ids = {s["id"] for s in self._suppliers}
        if self._rejected_ids == all_ids:
            self._done = True
            return -0.5, f"Rejected {name}. All suppliers eliminated -- procurement failed."

        remaining = len(all_ids) - len(self._rejected_ids)
        return 0.0, f"Rejected {name}. {remaining} supplier(s) still under consideration."

    # ------------------------------------------------------------------ #
    #  Grader / Final Score                                               #
    # ------------------------------------------------------------------ #

    def _compute_final_score(self, accepted_sid: int, was_deceived: bool) -> float:
        """
        Terminal reward emitted when the agent accepts a supplier.

        Weighted across four procurement dimensions:

          cost_efficiency (40%):
            How close the negotiated deal price is to the theoretical best possible
            price across all valid suppliers (those with required certs + quality >= 0.60).
            Accepting at the highest quoted price among valid suppliers = 0.0 on this
            component. Hitting the lowest min_price among valid suppliers = 0.40.
            Over-budget acceptance scores 0.0 regardless.

          cert_compliance (30%):
            Fraction of required RFQ certifications held by the accepted supplier.
            All certs present = 0.30. One missing cert halves this. None = 0.0.
            If no certs are required, full credit is granted automatically.

          quality_check (20%):
            Full credit (0.20) only if: (a) quality_report was explicitly requested
            before accept(), AND (b) the supplier's quality_score >= 0.60.
            Skipping the quality check = 0.0 here, regardless of actual quality.
            Requesting the report and finding poor quality = 0.05 (partial credit for
            due diligence, penalised for accepting anyway).

          due_diligence (10%):
            Proportion of queryable attributes checked: lead_time, moq, reliability,
            certifications. Each checked field is worth 0.04, capped at 0.10.

        Deception penalty:
            If the agent was deceived (accepted a deceptive supplier after the price
            revision), multiply the total by DECEPTION_PENALTY_MULTIPLIER (0.40).
            This models the real cost of being locked into a bad contract.

        Returns a value clamped to (SCORE_MIN, SCORE_MAX) -- the OpenEnv validator
        rejects exactly 0.0 or 1.0.
        """
        supplier = self._get_supplier(accepted_sid)
        rfq = self._task["rfq"]
        revealed = self._revealed[str(accepted_sid)]

        # 1. Cost efficiency (0.0 -- 0.40)
        final_price = self._best_offers[str(accepted_sid)]
        total_cost = final_price * rfq["quantity"]
        budget = rfq["budget"]

        if total_cost > budget:
            cost_score = 0.0
        else:
            valid_suppliers = [
                s for s in self._suppliers
                if all(c in s["certifications"] for c in rfq["required_certs"])
                and s["quality_score"] >= QUALITY_THRESHOLD
            ]
            if valid_suppliers:
                best_floor   = min(s["min_price"]     for s in valid_suppliers) * rfq["quantity"]
                worst_quoted = max(s["quoted_price"]   for s in valid_suppliers) * rfq["quantity"]
                spread = max(worst_quoted - best_floor, 1)
                cost_score = COST_EFFICIENCY_WEIGHT * max(0.0, (worst_quoted - total_cost) / spread)
            else:
                cost_score = 0.20  # no valid suppliers exist -- partial credit

        # 2. Certification compliance (0.0 -- 0.30)
        required_certs = rfq["required_certs"]
        if not required_certs:
            cert_score = CERT_COMPLIANCE_WEIGHT
        else:
            supplier_certs = supplier["certifications"]
            certs_met = sum(1 for c in required_certs if c in supplier_certs)
            cert_score = CERT_COMPLIANCE_WEIGHT * (certs_met / len(required_certs))

        # 3. Quality check (0.0 -- 0.20)
        if "quality_report" in revealed:
            quality_val = supplier["quality_score"]
            quality_score = QUALITY_CHECK_WEIGHT if quality_val >= QUALITY_THRESHOLD else 0.05
        else:
            quality_score = 0.0

        # 4. Due diligence (0.0 -- 0.10)
        diligence_fields = {"lead_time", "moq", "reliability", "certifications"}
        checks = len([k for k in revealed if k in diligence_fields])
        diligence_score = min(DUE_DILIGENCE_WEIGHT, checks * 0.04)

        total = cost_score + cert_score + quality_score + diligence_score
        if was_deceived:
            total *= DECEPTION_PENALTY_MULTIPLIER

        return round(min(SCORE_MAX, max(SCORE_MIN, total)), 3)

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
            if s["id"] in self._rejected_ids:
                status = "rejected"
            elif s["id"] == self._accepted_id:
                status = "accepted"
            else:
                status = "active"
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
        """
        Append decision-relevant context to every outbound message.

        Adds: steps remaining, unchecked certification warnings for active suppliers,
        quality report reminders, and a summary of revealed info. These hints guide
        the agent without giving away hidden values -- they flag *what to check*,
        not the check results.

        Skipped when the episode is already done (no further actions possible).
        """
        steps_remaining = self._task["max_steps"] - self._step_count
        if self._done or steps_remaining <= 0:
            return base_message

        required_certs = self._task["rfq"]["required_certs"]
        parts = [base_message]
        parts.append(f"Steps remaining: {steps_remaining}/{self._task['max_steps']}.")

        # Flag active suppliers with unchecked certifications when certs are required
        if required_certs:
            unchecked_certs = [
                s["name"] for s in self._suppliers
                if s["id"] not in self._rejected_ids
                and s["id"] != self._accepted_id
                and "certifications" not in self._revealed.get(str(s["id"]), {})
            ]
            if unchecked_certs:
                parts.append(
                    f"Cert check pending for: {', '.join(unchecked_certs)}. "
                    f"Required: {required_certs}."
                )

        # Flag active suppliers without a quality report
        no_quality = [
            s["name"] for s in self._suppliers
            if s["id"] not in self._rejected_ids
            and s["id"] != self._accepted_id
            and "quality_report" not in self._revealed.get(str(s["id"]), {})
        ]
        if no_quality:
            parts.append(f"Quality report not yet requested for: {', '.join(no_quality)}.")

        # Summarise what's already known about active suppliers
        known_summaries = []
        for s in self._suppliers:
            if s["id"] in self._rejected_ids:
                continue
            revealed = self._revealed.get(str(s["id"]), {})
            if revealed:
                kvs = ", ".join(f"{k}={v}" for k, v in revealed.items())
                known_summaries.append(f"{s['name']}: {kvs}")
        if known_summaries:
            parts.append(f"Known: {'; '.join(known_summaries)}.")

        return " | ".join(parts)
