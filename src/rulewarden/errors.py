"""Exception hierarchy. Every error maps to fail-closed handling in the runner (P5)."""


class RulewardenError(Exception):
    """Base class for all rulewarden errors."""


class SchemaError(RulewardenError):
    """A rule file does not conform to the schema."""


class LoadError(RulewardenError):
    """Rules or configuration could not be loaded."""


class LockError(RulewardenError):
    """The rule set does not match rules.lock, or the lock is unreadable."""


class EngineError(RulewardenError):
    """A check engine failed while evaluating a rule."""


class BudgetExceeded(RulewardenError):
    """Evaluation exceeded its time or size budget."""


class DiffError(RulewardenError):
    """A diff could not be obtained or parsed."""
