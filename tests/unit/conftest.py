"""Unit-suite only: the hypothesis profile."""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "unit", deadline=None, max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
settings.load_profile("unit")
