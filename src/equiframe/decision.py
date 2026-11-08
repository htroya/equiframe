"""Three-state OR preserving incomplete alerts; MAD is deliberately absent."""

from equiframe.detector_types import ComponentDecision, HybridDecision
from equiframe.rule_types import RuleEvaluation


def combine_decisions(
    r: ComponentDecision | RuleEvaluation, m: ComponentDecision
) -> HybridDecision:
    if isinstance(r, RuleEvaluation):
        rule = RuleEvaluation.model_validate(r)
        r = ComponentDecision(
            decision=rule.decision,
            complete=rule.complete,
            reason=None if rule.complete else rule.diagnostic or "incomplete_rules",
        )
    r = ComponentDecision.model_validate(r)
    m = ComponentDecision.model_validate(m)
    complete = r.complete and m.complete
    return HybridDecision(
        r=r,
        m=m,
        result=ComponentDecision(
            decision=(
                "alert"
                if "alert" in (r.decision, m.decision)
                else "no_alert"
                if r.decision == m.decision == "no_alert"
                else "not_evaluable"
            ),
            complete=complete,
            reason=None if complete else "incomplete_components",
        ),
    )
