# Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service
# Terms and the SOW between the parties dated 2025.

"""Event processing utilities for chat handler."""

import json
from typing import Any


# Content Block Context for tracking state across events
class ContentBlockContext:
    """Class to maintain context for a content block across multiple events."""

    def __init__(self):
        self.tool_name = ''
        self.tool_id = ''
        self.accumulated_tool_input = ''
        self.block_type = None  # "text", "tool_call", "reasoning"
        self.start_time = None
        self.block_sequence_counter = 0  # Tracks sequence within this block
        self.metadata = {}


# Event type helpers
def is_init_event(event: Any) -> bool:
    """Check if event is an initialization event to skip."""
    if not isinstance(event, dict):
        return False

    return any(key in event for key in ['init_event_loop', 'start', 'start_event_loop'])


def is_enriched_event(event: Any) -> bool:
    """Determine if an event is an enriched event (vs raw API event)."""
    if not isinstance(event, dict):
        return False

    # Check for enriched event indicators
    enriched_indicators = [
        'agent',
        'event_loop_metrics',
        'event_loop_cycle_id',
        'current_tool_use',
        'reasoning',
        'reasoningText',
    ]

    # If it has "data" and "delta" together, it's likely enriched
    if 'data' in event and 'delta' in event:
        return True

    # Check for other enrichment indicators
    return any(indicator in event for indicator in enriched_indicators)


def get_event_type(event: Any) -> str:
    """Get a human-readable event type for logging."""
    if not isinstance(event, dict):
        return type(event).__name__

    if 'init_event_loop' in event:
        return 'init_event_loop'
    elif 'start' in event:
        return 'start'
    elif 'start_event_loop' in event:
        return 'start_event_loop'
    elif 'event' in event:
        event_data = event['event']
        if isinstance(event_data, dict):
            if 'messageStart' in event_data:
                return 'messageStart'
            elif 'contentBlockStart' in event_data:
                return 'contentBlockStart'
            elif 'contentBlockDelta' in event_data:
                return 'contentBlockDelta'
            elif 'contentBlockStop' in event_data:
                return 'contentBlockStop'
            elif 'messageStop' in event_data:
                return 'messageStop'
            elif 'metadata' in event_data:
                return 'metadata'
            elif any(key.endswith('Exception') for key in event_data):
                return 'error'
    elif 'data' in event and 'delta' in event:
        return 'enriched_content'

    return 'unknown'


def parse_tool_args(raw_args: str) -> dict[str, Any]:
    """Parse tool arguments from JSON string."""
    try:
        # Try to parse as complete JSON first
        return json.loads(raw_args)
    except json.JSONDecodeError:
        # If it fails, it might be partial JSON - return empty dict for now
        return {}


# Stop reason constants
FINAL_STOP_REASONS: set[str] = {
    'end_turn',
    'guardrail_intervened',
    'stop_sequence',
    'max_tokens',
    'content_filtered',
}

CONTINUATION_STOP_REASONS: set[str] = {'tool_use'}
