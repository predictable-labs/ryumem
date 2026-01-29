"""
Legal Contract Processing - Workflow Demonstration

This example demonstrates workflow orchestration with Google ADK + Ryumem.
The agent creates plans, stores them, executes them, and updates them if issues arise.

Prerequisites:
    pip install google-adk ryumem python-dateutil

Setup:
    export GOOGLE_API_KEY=your_api_key
"""

import os
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import logging
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Check if Google ADK is installed
try:
    from google.adk.agents import Agent
    from google.adk.tools import FunctionTool
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
except ImportError:
    print("ERROR: Google ADK not installed. Run: pip install google-adk")
    exit(1)

from ryumem import Ryumem
from ryumem.integrations import add_memory_to_agent, wrap_runner_with_tracking

# App configuration
APP_NAME = "legal_contracts_workflow"
USER_ID = "legal_team_1"
MODEL_ID = "gemini-2.0-flash-exp"
CONTRACT_FILE = "sample_contract.txt"

# Contract text loaded from external file
SAMPLE_CONTRACT = ""

def load_contract():
    """Load contract from external file."""
    global SAMPLE_CONTRACT
    script_dir = os.path.dirname(os.path.abspath(__file__))
    contract_path = os.path.join(script_dir, CONTRACT_FILE)

    try:
        with open(contract_path, 'r') as f:
            SAMPLE_CONTRACT = f.read()
        print(f"✓ Loaded contract from {CONTRACT_FILE} ({len(SAMPLE_CONTRACT)} characters)")
    except FileNotFoundError:
        print(f"ERROR: Contract file not found: {contract_path}")
        exit(1)


# Contract will be loaded from sample_contract.txt at runtime


# ============================================================================
# TOOL 1: get_chunk_by_term
# ============================================================================

def get_chunk_by_term(term: str, context_chars: int = 200) -> Dict:
    """
    Locate text chunks containing a specific term.

    Args:
        term: Search term to find in the document
        context_chars: Number of characters to include before and after the term

    Returns:
        dict: Contains:
            - found: bool - whether the term was found
            - chunks: list of dicts with {text, start_pos, end_pos, term_pos}
            - count: number of occurrences found
            - message: status message
    """
    chunks = []

    # Case-insensitive search
    pattern = re.compile(re.escape(term), re.IGNORECASE)

    for match in pattern.finditer(SAMPLE_CONTRACT):
        term_pos = match.start()

        # Calculate chunk boundaries
        start_pos = max(0, term_pos - context_chars)
        end_pos = min(len(SAMPLE_CONTRACT), term_pos + len(term) + context_chars)

        chunk_text = SAMPLE_CONTRACT[start_pos:end_pos]

        chunks.append({
            "text": chunk_text,
            "start_pos": start_pos,
            "end_pos": end_pos,
            "term_pos": term_pos,
            "term": term
        })

    if chunks:
        return {
            "found": True,
            "chunks": chunks,
            "count": len(chunks),
            "message": f"Found {len(chunks)} occurrence(s) of '{term}'"
        }
    else:
        return {
            "found": False,
            "chunks": [],
            "count": 0,
            "message": f"Term '{term}' not found in document"
        }


# ============================================================================
# TOOL 2: get_chunk_regex
# ============================================================================

def get_chunk_regex(regex_pattern: str, context_chars: int = 200) -> Dict:
    """
    Locate text chunks matching a regular expression pattern.

    Args:
        regex_pattern: Regular expression pattern to search for
        context_chars: Number of characters to include before and after the match

    Returns:
        dict: Contains:
            - found: bool - whether matches were found
            - chunks: list of dicts with {text, start_pos, end_pos, match_pos, matched_text}
            - count: number of matches found
            - message: status message
    """
    try:
        pattern = re.compile(regex_pattern, re.IGNORECASE)
    except re.error as e:
        return {
            "found": False,
            "chunks": [],
            "count": 0,
            "error": f"Invalid regex pattern: {e}",
            "message": f"Regex error: {e}"
        }

    chunks = []

    for match in pattern.finditer(SAMPLE_CONTRACT):
        match_pos = match.start()
        matched_text = match.group(0)

        # Calculate chunk boundaries
        start_pos = max(0, match_pos - context_chars)
        end_pos = min(len(SAMPLE_CONTRACT), match_pos + len(matched_text) + context_chars)

        chunk_text = SAMPLE_CONTRACT[start_pos:end_pos]

        chunks.append({
            "text": chunk_text,
            "start_pos": start_pos,
            "end_pos": end_pos,
            "match_pos": match_pos,
            "matched_text": matched_text
        })

    if chunks:
        return {
            "found": True,
            "chunks": chunks,
            "count": len(chunks),
            "message": f"Found {len(chunks)} match(es) for pattern '{regex_pattern}'"
        }
    else:
        return {
            "found": False,
            "chunks": [],
            "count": 0,
            "message": f"No matches found for pattern '{regex_pattern}'"
        }


# ============================================================================
# TOOL 3: get_chunk_by_position
# ============================================================================

def get_chunk_by_position(start_pos: int, end_pos: int) -> Dict:
    """
    Extract text chunk by exact character positions.

    Args:
        start_pos: Starting position (0-indexed)
        end_pos: Ending position (exclusive)

    Returns:
        dict: Contains:
            - valid: bool - whether positions are valid
            - text: extracted text chunk
            - start_pos: actual start position used
            - end_pos: actual end position used
            - length: length of extracted text
            - message: status message
    """
    doc_length = len(SAMPLE_CONTRACT)

    # Validate positions
    if start_pos < 0 or end_pos > doc_length or start_pos >= end_pos:
        return {
            "valid": False,
            "text": "",
            "start_pos": start_pos,
            "end_pos": end_pos,
            "length": 0,
            "message": f"Invalid positions: start={start_pos}, end={end_pos}, doc_length={doc_length}"
        }

    chunk_text = SAMPLE_CONTRACT[start_pos:end_pos]

    return {
        "valid": True,
        "text": chunk_text,
        "start_pos": start_pos,
        "end_pos": end_pos,
        "length": len(chunk_text),
        "message": f"Extracted {len(chunk_text)} characters from position {start_pos} to {end_pos}"
    }


# ============================================================================
# TOOL 4: check_exists_in_text
# ============================================================================

def check_exists_in_text(text_to_check: str, allow_partial: bool = False) -> Dict:
    """
    Validate that extracted text truly exists in the document.

    Args:
        text_to_check: Text to verify exists in the document
        allow_partial: If True, check for partial matches (substring search)

    Returns:
        dict: Contains:
            - exists: bool - whether text exists in document
            - exact_match: bool - whether it's an exact match
            - positions: list of positions where text was found
            - count: number of occurrences
            - message: status message
    """
    positions = []

    if allow_partial:
        # Substring search
        start = 0
        while True:
            pos = SAMPLE_CONTRACT.find(text_to_check, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
    else:
        # Exact match with word boundaries
        # First try exact substring match
        start = 0
        while True:
            pos = SAMPLE_CONTRACT.find(text_to_check, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

    exists = len(positions) > 0

    return {
        "exists": exists,
        "exact_match": exists and not allow_partial,
        "positions": positions,
        "count": len(positions),
        "message": f"Text {'found' if exists else 'not found'} in document ({len(positions)} occurrence(s))"
    }


# ============================================================================
# TOOL 5: is_valid_date
# ============================================================================

def is_valid_date(date_string: str) -> Dict:
    """
    Validate that a string represents a valid calendar date.

    Args:
        date_string: String to validate as a date

    Returns:
        dict: Contains:
            - valid: bool - whether string is a valid date
            - parsed_date: ISO format date if valid, None otherwise
            - format_detected: detected date format
            - message: status message
    """
    try:
        # Use dateutil parser for flexible date parsing
        parsed = date_parser.parse(date_string, fuzzy=False)

        return {
            "valid": True,
            "parsed_date": parsed.date().isoformat(),
            "format_detected": "auto-detected",
            "year": parsed.year,
            "month": parsed.month,
            "day": parsed.day,
            "message": f"Valid date: {parsed.date().isoformat()}"
        }
    except (ValueError, date_parser.ParserError) as e:
        return {
            "valid": False,
            "parsed_date": None,
            "format_detected": None,
            "message": f"Invalid date format: {e}"
        }


# ============================================================================
# TOOL 6: llm_trigger
# ============================================================================

def llm_trigger(text_chunk: str, prompt: str) -> Dict:
    """
    Use a small LLM to extract structured information from a text chunk.
    This is a synchronous wrapper that will be used by the workflow engine.

    Args:
        text_chunk: Text chunk to analyze
        prompt: Prompt describing what information to extract

    Returns:
        dict: Contains:
            - success: bool - whether LLM extraction succeeded
            - extracted_data: extracted structured information
            - raw_response: raw LLM response
            - message: status message
    """
    try:
        from google import genai
        from google.genai import types as genai_types

        # Create a simple client for one-off generation
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

        # Construct the full prompt
        full_prompt = f"""{prompt}

Text chunk to analyze:
{text_chunk}

Please extract the requested information and return it in a structured format."""

        # Generate response
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=full_prompt
        )

        extracted_text = response.text

        return {
            "success": True,
            "extracted_data": extracted_text,
            "raw_response": extracted_text,
            "message": f"Successfully extracted data using LLM"
        }

    except Exception as e:
        return {
            "success": False,
            "extracted_data": None,
            "raw_response": None,
            "error": str(e),
            "message": f"LLM extraction failed: {e}"
        }


# ============================================================================
# TOOL 7: resolve_date
# ============================================================================

def resolve_date(
    base_date: str,
    relative_expression: str
) -> Dict:
    """
    Deterministically resolve a relative date expression based on an absolute base date.

    Args:
        base_date: Absolute base date in ISO format (YYYY-MM-DD)
        relative_expression: Relative expression (e.g., "6 months after", "30 days before")

    Returns:
        dict: Contains:
            - success: bool - whether resolution succeeded
            - resolved_date: resolved absolute date in ISO format
            - base_date: base date used
            - expression: relative expression used
            - message: status message
    """
    try:
        # Parse base date
        base = datetime.fromisoformat(base_date)

        # Parse relative expression
        # Patterns: "N days/months/years after/before"
        pattern = r'(\d+)\s+(day|days|month|months|year|years)\s+(after|before)'
        match = re.match(pattern, relative_expression.lower().strip())

        if not match:
            return {
                "success": False,
                "resolved_date": None,
                "base_date": base_date,
                "expression": relative_expression,
                "message": f"Could not parse relative expression: '{relative_expression}'"
            }

        amount = int(match.group(1))
        unit = match.group(2)
        direction = match.group(3)

        # Determine the time delta
        if 'day' in unit:
            delta = timedelta(days=amount)
        elif 'month' in unit:
            delta = relativedelta(months=amount)
        elif 'year' in unit:
            delta = relativedelta(years=amount)
        else:
            raise ValueError(f"Unknown time unit: {unit}")

        # Apply direction
        if direction == "after":
            resolved = base + delta
        else:  # before
            resolved = base - delta

        return {
            "success": True,
            "resolved_date": resolved.date().isoformat(),
            "base_date": base_date,
            "expression": relative_expression,
            "amount": amount,
            "unit": unit,
            "direction": direction,
            "message": f"Resolved to {resolved.date().isoformat()}"
        }

    except Exception as e:
        return {
            "success": False,
            "resolved_date": None,
            "base_date": base_date,
            "expression": relative_expression,
            "error": str(e),
            "message": f"Date resolution failed: {e}"
        }


# ============================================================================
# Demo Runner
# ============================================================================

async def run_demo():
    """Run the workflow demonstration."""
    load_contract()

    print("\n" + "=" * 80)
    print("📄 Legal Contract Workflow - Google ADK + Ryumem")
    print("=" * 80)
    print("\nDEMONSTRATING WORKFLOW ORCHESTRATION:")
    print("  • Agent creates a plan before executing")
    print("  • Plan is stored in memory")
    print("  • Agent executes the plan step by step")
    print("  • If issues arise, agent updates the plan")
    print("  • Continues execution with updated plan")
    print("=" * 80)
    print()

    # Create tools
    chunk_by_term_tool = FunctionTool(func=get_chunk_by_term)
    chunk_by_regex_tool = FunctionTool(func=get_chunk_regex)
    chunk_by_position_tool = FunctionTool(func=get_chunk_by_position)
    check_exists_tool = FunctionTool(func=check_exists_in_text)
    validate_date_tool = FunctionTool(func=is_valid_date)
    llm_tool = FunctionTool(func=llm_trigger)
    resolve_date_tool = FunctionTool(func=resolve_date)

    # Create agent with workflow-oriented instructions
    legal_agent = Agent(
        model=MODEL_ID,
        name='legal_workflow_agent',
        instruction="""You are a legal contract analyst. Answer queries by calling the analysis tools directly.

AVAILABLE ANALYSIS TOOLS:
1. get_chunk_by_term(term, context_chars) - Find text chunks containing a specific term (e.g., 'Effective Date')
2. get_chunk_regex(regex_pattern, context_chars) - Find chunks matching a regex pattern
3. get_chunk_by_position(start_pos, end_pos) - Extract text by exact positions
4. check_exists_in_text(text_to_check, allow_partial) - Verify text exists in document
5. is_valid_date(date_string) - Validate if a string is a valid date
6. llm_trigger(text_chunk, prompt) - Extract structured data using LLM
7. resolve_date(base_date, relative_expression) - Resolve relative dates (e.g., '6 months after')

WORKFLOW TOOLS (use these for complex multi-step analysis):
- save_workflow(workflow_definition) - Save a workflow plan
- start_workflow(workflow_id, initial_variables) - Execute a saved workflow
- continue_workflow(session_id, response) - Continue a paused workflow

🚨 CRITICAL - WORKFLOW SYNTAX REQUIREMENTS:
Workflows will be REJECTED by the server if they don't follow these rules:
1. tool_name: MUST be the exact name of an available tool (e.g., "get_chunk_by_term"). NEVER null.
2. input_params: MUST be a dictionary with ALL required arguments. NEVER empty for tool nodes.
3. Node Dependencies: Must be a list of node_ids that must complete first.
4. Variable References: Use dollar-curly-brace syntax: "$[node_id]". Example: {"date": "$[step1]"} // MUST use curly braces

Complete Workflow Example:
{
    "name": "Contract Term Calculation",
    "description": "Extracts effective date and calculates end date",
    "query_templates": ["When does the contract end?", "Calculate end date"],
    "nodes": [
        {
            "node_id": "find_date",
            "node_type": "tool",
            "tool_name": "get_chunk_by_term",
            "input_params": {"term": "Effective Date", "context_chars": 200},
            "dependencies": []
        },
        {
            "node_id": "verify_date",
            "node_type": "tool",
            "tool_name": "is_valid_date",
            "input_params": {"date_string": "$[find_date]"}, // use curly braces here
            "dependencies": ["find_date"]
        },
        {
            "node_id": "calculate",
            "node_type": "tool",
            "tool_name": "resolve_date",
            "input_params": {
                "base_date": "$[verify_date]", // use curly braces here
                "relative_expression": "6 months after"
            },
            "dependencies": ["verify_date"]
        }
    ]
}

HOW TO PROCEED:
1. If the user query is complex, DESIGN the workflow first.
2. SAVE the workflow using save_workflow.
3. START the workflow using start_workflow.
4. When workflow finishes or pauses, explain the results to the user.

IMPORTANT: You MUST NOT return null for tool_name or empty dict for input_params in workflow nodes.""",
        tools=[
            chunk_by_term_tool,
            chunk_by_regex_tool,
            chunk_by_position_tool,
            check_exists_tool,
            validate_date_tool,
            llm_tool,
            resolve_date_tool
        ]
    )

    print("✓ Agent created with 7 tools and workflow-oriented instructions")
    print()

    # Add memory and tracking
    ryumem = Ryumem(
        track_tools=True,
        augment_queries=True,
        similarity_threshold=0.3,
        top_k_similar=5,
    )

    legal_agent = add_memory_to_agent(legal_agent, ryumem)

    print("✓ Memory and tool tracking enabled")
    print()

    # Print available tools for debugging
    print("🔧 Available tools:")
    for i, tool in enumerate(legal_agent.tools, 1):
        tool_name = getattr(tool, 'name', getattr(tool, '__name__', 'unknown'))
        print(f"   {i}. {tool_name}")
    print()

    # Session setup
    session_id = "legal_contract_session_001"
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )

    runner = Runner(
        agent=legal_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    runner = wrap_runner_with_tracking(runner, legal_agent)

    print("✓ Runner configured")
    print()

    # Test with one query
    query = "What is the end date of the Initial Term?"

    print(f"\n{'='*80}")
    print(f"👤 User: {query}")
    print(f"{'='*80}\n")

    content = types.Content(role='user', parts=[types.Part(text=query)])

    try:
        print("📤 Sending query to runner...")
        events = runner.run(
            user_id=USER_ID,
            session_id=session_id,
            new_message=content
        )
        print("📥 Events received from runner")

        # Process all events with detailed logging
        print("📋 Processing events:")
        final_response = None
        event_count = 0

        for event in events:
            event_count += 1
            print(f"\n--- Event {event_count} ---")
            print(f"   Type: {type(event).__name__}")
            print(f"   Is final: {event.is_final_response()}")

            # Debug: print event attributes
            print(f"   Has content attr: {hasattr(event, 'content')}")
            if hasattr(event, 'content'):
                print(f"   Content is None: {event.content is None}")
                if event.content:
                    print(f"   Content type: {type(event.content).__name__}")
                    print(f"   Has parts: {hasattr(event.content, 'parts')}")
                    if hasattr(event.content, 'parts'):
                        print(f"   Parts: {event.content.parts}")

            # Check for tool calls (different ways)
            if hasattr(event, 'tool_calls') and event.tool_calls:
                print(f"   Tool calls: {len(event.tool_calls)}")
                for tc in event.tool_calls:
                    tc_name = getattr(tc, 'name', 'unknown')
                    print(f"     - {tc_name}")

            # Try get_function_calls()
            if hasattr(event, 'get_function_calls'):
                func_calls = event.get_function_calls()
                if func_calls:
                    print(f"   Function calls: {len(func_calls)}")
                    for fc in func_calls:
                        print(f"     - Name: {fc.name if hasattr(fc, 'name') else 'unknown'}")
                        print(f"       Args: {fc.args if hasattr(fc, 'args') else 'N/A'}")

            # Try get_function_responses()
            if hasattr(event, 'get_function_responses'):
                func_responses = event.get_function_responses()
                if func_responses:
                    print(f"   Function responses: {len(func_responses)}")
                    for fr in func_responses:
                        print(f"     - Name: {fr.name if hasattr(fr, 'name') else 'unknown'}")
                        resp_preview = str(fr.response)[:100] if hasattr(fr, 'response') else 'N/A'
                        print(f"       Response: {resp_preview}...")

            # Check for content
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts and len(event.content.parts) > 0:
                    first_part = event.content.parts[0]
                    if first_part:
                        text_preview = first_part.text if hasattr(first_part, 'text') else 'no text'
                        if text_preview:
                            print(f"   Content preview: {str(text_preview)[:100]}...")
                        else:
                            print(f"   Content preview: (empty)")

                        if event.is_final_response():
                            final_response = first_part.text if hasattr(first_part, 'text') else None

            # Debug: print all event attributes
            print(f"   Event dir: {[a for a in dir(event) if not a.startswith('_')]}")

        print(f"\n{'='*80}")
        if final_response:
            print(f"🤖 Agent Final Response:\n{final_response}")
        else:
            print("⚠️  No final response received")
        print(f"{'='*80}")

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("✅ Workflow demonstration completed!")
    print("="*80)


async def main():
    """Entry point."""
    await run_demo()


if __name__ == "__main__":
    # Check for required environment variables
    if not os.getenv("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable not set")
        print("Run: export GOOGLE_API_KEY=your_api_key")
        exit(1)

    asyncio.run(main())
