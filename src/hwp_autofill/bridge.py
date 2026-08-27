from .planner import build_proposals, proposals_to_plan

def build_autofill_bundle(analysis, conversation_facts):
    proposal_bundle = build_proposals(analysis.get("fields", []), conversation_facts)
    return {
        "document": {"input": analysis.get("input"), "format": analysis.get("format")},
        "facts": conversation_facts,
        **proposal_bundle,
        "plan": proposals_to_plan(proposal_bundle),
    }
