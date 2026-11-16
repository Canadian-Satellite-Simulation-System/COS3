"""
Sends commands to COSMOS and records the outcome.

    record = sender.send(target, name, raw_values, confirm_hazardous=False)
    record = sender.resend(record_id, confirm_hazardous=False)

Each send:
  1. validates the values (commands/validation.py) -> ValidationFailed(errors) if any are wrong
  2. checks for hazards (hazardous command, or a hazardous state chosen)
     -> ConfirmationRequired(reason) unless confirm_hazardous is True
  3. sends with cmd(), or cmd_no_hazardous_check() when the operator confirmed a hazard
  4. records the outcome in the CommandHistory: sent, rejected (COSMOS refused) or failed

NotAuthenticated propagates (the operator has to log in again); nothing is recorded then.
"""

from cosmos_client import CosmosError, CosmosRejected, CosmosUnavailable, HazardousCommand, NotAuthenticated
from commands.history import Status
from commands.validation import validate


class ValidationFailed(Exception):
    """Some values are invalid; errors maps parameter names to messages. Nothing was sent."""

    def __init__(self, errors):
        super().__init__("Some parameter values are invalid.")
        self.errors = errors


class ConfirmationRequired(Exception):
    """The command is hazardous; resend with confirm_hazardous=True. Nothing was sent."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def hazard_reason(definition, values):
    """Why sending these values is hazardous, or None."""
    if definition.hazardous:
        return definition.hazardous_description or f"{definition.name} is a hazardous command."
    for p in definition.parameters:
        if p.name in values and p.states and p.hazardous_states:
            chosen = next((s for s, v in p.states.items() if v == values[p.name]), None)
            if chosen in p.hazardous_states:
                return f"{p.name} = {chosen} is a hazardous setting."
    return None


def to_cosmos(values):
    """Typed values in the form COSMOS's JSON API expects (binary as {"json_class": "String", "raw": [...]})."""
    return {
        name: {"json_class": "String", "raw": list(v)} if isinstance(v, (bytes, bytearray)) else v
        for name, v in values.items()
    }


def _path(target):
    return "RADIO" if target.endswith("_RADIO") else "DEBUG"


def _entered(raw_values):
    """The values worth showing in the history: as typed, blank ones left out."""
    return {k: str(v) for k, v in (raw_values or {}).items() if v is not None and str(v).strip() != ""}


class CommandSender:
    def __init__(self, client, catalog, history):
        self._client = client
        self._catalog = catalog
        self._history = history

    def send(self, target, name, raw_values, confirm_hazardous=False, resend_of=None):
        """Validate, check hazards, send and record. See the module docstring."""
        definition = self._catalog.get_command(target, name)  # UnknownCommand / CosmosError
        values, errors = validate(definition, raw_values)
        if errors:
            raise ValidationFailed(errors)

        reason = hazard_reason(definition, values)
        if reason and not confirm_hazardous:
            raise ConfirmationRequired(reason)
        confirmed = bool(reason) and confirm_hazardous

        record = dict(target=target, name=name, path=_path(target), values=_entered(raw_values),
                      hazardous_confirmed=confirmed, resend_of=resend_of)
        try:
            self._client.send_command(target, name, to_cosmos(values), hazardous_confirmed=confirmed)
        except HazardousCommand as err:
            # COSMOS knows of a hazard the definition didn't show: ask the operator first
            if not confirm_hazardous:
                raise ConfirmationRequired(str(err)) from err
            return self._history.add(**record, status=Status.REJECTED, error=str(err))
        except NotAuthenticated:
            raise
        except CosmosRejected as err:
            return self._history.add(**record, status=Status.REJECTED, error=str(err))
        except CosmosUnavailable as err:
            return self._history.add(**record, status=Status.FAILED,
                                     error=f"{err} It may or may not have been sent.")
        except CosmosError as err:
            return self._history.add(**record, status=Status.FAILED, error=str(err))
        return self._history.add(**record, status=Status.SENT)

    def resend(self, record_id, confirm_hazardous=False):
        """Send a recorded command again with the same values (checked again first)."""
        previous = self._history.get(record_id)  # UnknownRecord
        return self.send(previous.target, previous.name, previous.values, confirm_hazardous, resend_of=previous.id)
