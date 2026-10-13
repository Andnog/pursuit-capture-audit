"""Public action menu, validity masks and the fallback rule.

The menu is data, read from the domain configuration, so that the contract and the code
cannot disagree about which actions exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CONTRACT_VERSION, load_domain, validate

FALLBACK_ACTION_ID = "HOLD_LANE"


@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    code: int
    parameters: tuple[str, ...]
    always_valid: bool


def action_menu(domain: dict | None = None) -> dict[str, ActionSpec]:
    domain = domain or load_domain()
    out: dict[str, ActionSpec] = {}
    for entry in domain["action_menu"]["actions"]:
        out[entry["action_id"]] = ActionSpec(
            action_id=entry["action_id"],
            code=entry["code"],
            parameters=tuple(entry.get("parameters", ())),
            always_valid=bool(entry.get("always_valid", False)),
        )
    return out


def build_action(
    vehicle_id: str,
    action_id: str,
    valid: bool,
    parameters: dict | None = None,
    invalid_reason: str | None = None,
    domain: dict | None = None,
) -> dict:
    """Build and validate one action record.

    An invalid action must carry a reason. An action recorded as unusable with no
    explanation is indistinguishable from a masking bug.
    """
    menu = action_menu(domain)
    if action_id not in menu:
        raise KeyError(f"{action_id!r} is not in the public action menu: {sorted(menu)}")
    if not valid and not invalid_reason:
        raise ValueError("an invalid action must record invalid_reason")
    spec = menu[action_id]
    record = {
        "contract_version": CONTRACT_VERSION,
        "vehicle_id": vehicle_id,
        "action_id": action_id,
        "action_code": spec.code,
        "valid": valid,
        "invalid_reason": invalid_reason,
        "parameters": dict(parameters or {}),
    }
    unexpected = set(record["parameters"]) - set(spec.parameters)
    if unexpected:
        raise ValueError(f"{action_id} does not take parameters {sorted(unexpected)}")
    validate("action", record)
    return record


def apply_mask(actions: list[dict]) -> list[dict]:
    """The selectable subset: actions whose validity bit is set."""
    return [a for a in actions if a["valid"]]


def choose_with_fallback(actions: list[dict], chosen_index: int | None) -> tuple[dict, str]:
    """Return the executed action and the decision label.

    With no valid action the contract-defined fallback is used. `HOLD_LANE` is declared
    `always_valid` in the domain configuration, so the fallback always exists and the
    selector never has to invent an action.
    """
    selectable = apply_mask(actions)
    if chosen_index is not None and 0 <= chosen_index < len(selectable):
        return selectable[chosen_index], "SELECTED"
    for action in actions:
        if action["action_id"] == FALLBACK_ACTION_ID:
            return action, "FALLBACK"
    raise ValueError(
        "no valid action and no fallback present; the action menu violates its contract"
    )
