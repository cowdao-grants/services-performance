"""Scenario management and validation."""

from .config_validation import (
    ConfigValidationResult,
    ConfigValidator,
    ValidationError,
    ValidationWarning,
    validate_token_address,
)
from .defaults import (
    ConfigurationMerger,
    DefaultsError,
    DefaultsLoader,
    load_with_defaults,
)
from .inheritance import (
    CircularDependencyError,
    InheritanceError,
    InheritanceResolver,
    resolve_inheritance,
)
from .profiles import (
    ProfileError,
    ProfileNotFoundError,
    ProfileSelector,
    apply_profile_if_requested,
)
from .templates import (
    ParameterError,
    TemplateError,
    TemplateExpander,
    TemplateNotFoundError,
    expand_template,
)
from .validation import (
    SuccessCriteriaValidator,
    ValidationFailure,
    ValidationResult,
    display_validation_result,
)

__all__ = [
    # Success criteria validation (runtime results)
    "SuccessCriteriaValidator",
    "ValidationFailure",
    "ValidationResult",
    "display_validation_result",
    # Configuration validation (before execution)
    "ConfigValidator",
    "ConfigValidationResult",
    "ValidationError",
    "ValidationWarning",
    "validate_token_address",
    # Inheritance resolution
    "CircularDependencyError",
    "InheritanceError",
    "InheritanceResolver",
    "resolve_inheritance",
    # Defaults and precedence
    "ConfigurationMerger",
    "DefaultsError",
    "DefaultsLoader",
    "load_with_defaults",
    # Profile-based overrides
    "ProfileError",
    "ProfileNotFoundError",
    "ProfileSelector",
    "apply_profile_if_requested",
    # Template expansion
    "ParameterError",
    "TemplateError",
    "TemplateExpander",
    "TemplateNotFoundError",
    "expand_template",
]
