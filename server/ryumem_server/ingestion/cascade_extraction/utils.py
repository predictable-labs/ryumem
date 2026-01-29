"""
Shared utilities for cascade extraction stages.

Provides common template loading and rendering functionality.
"""

import re
from pathlib import Path


# Load prompt templates
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt template from file."""
    with open(PROMPTS_DIR / filename, "r") as f:
        return f.read()


def render_template(template: str, **kwargs) -> str:
    """Simple Jinja2-style template rendering."""
    result = template
    for key, value in kwargs.items():
        # Handle simple variable replacement
        result = result.replace("{{ " + key + " }}", str(value) if value else "")
        result = result.replace("{{" + key + "}}", str(value) if value else "")

    # Handle conditional blocks {% if var %}...{% endif %}
    for key, value in kwargs.items():
        if_pattern = rf'{{% if {key} %}}(.*?){{% endif %}}'
        if value:
            # Keep the content inside the if block
            result = re.sub(if_pattern, r'\1', result, flags=re.DOTALL)
        else:
            # Remove the entire if block
            result = re.sub(if_pattern, '', result, flags=re.DOTALL)

    return result.strip()
