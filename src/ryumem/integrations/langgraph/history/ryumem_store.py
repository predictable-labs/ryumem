import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ryumem import Ryumem
from ryumem.core.metadata_models import EpisodeMetadata, ToolExecution, QueryRun
from .base import HistoryStore

logger = logging.getLogger(__name__)

class RyumemStore(HistoryStore):
    """
    History store implementation using Ryumem.
    
    Reuses EpisodeMetadata and ToolExecution schemas to ensure compatibility
    with existing dashboards and tools.
    """

    def __init__(self, ryumem: Ryumem):
        self.ryumem = ryumem

    def save_step(self, session_id: str, step: Dict[str, Any], user_id: str) -> None:
        """
        Save a step to Ryumem.
        
        Args:
            session_id: The session identifier.
            step: Dictionary containing step details (tool_name, input, output, etc.)
            user_id: The user identifier.
        """
        try:
            # 1. Get or create episode for this session
            episode = self.ryumem.get_episode_by_session_id(session_id)
            
            if not episode:
                # Create new episode
                # We use source="message" or "json" depending on preference, 
                # but "message" is standard for chat/agent sessions.
                # We set integration="langgraph" in metadata.
                
                metadata = EpisodeMetadata(integration="langgraph")
                # Create an initial empty run for this session
                run_id = f"run_{int(datetime.utcnow().timestamp())}"
                query_run = QueryRun(
                    run_id=run_id,
                    user_id=user_id,
                    timestamp=datetime.utcnow().isoformat(),
                    query="LangGraph Session Started", # Placeholder or initial input if available
                    agent_response="",
                    tools_used=[]
                )
                metadata.add_query_run(session_id, query_run)
                
                self.ryumem.add_episode(
                    content=f"LangGraph Session {session_id}",
                    user_id=user_id,
                    session_id=session_id,
                    source="message",
                    metadata=metadata.model_dump()
                )
                episode = self.ryumem.get_episode_by_session_id(session_id)
                
            if not episode:
                logger.error(f"Failed to create/retrieve episode for session {session_id}")
                return

            # 2. Parse existing metadata
            metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else {}
            # Handle string metadata if necessary (though Ryumem client handles it)
            if isinstance(metadata_dict, str):
                metadata_dict = json.loads(metadata_dict)
                
            episode_metadata = EpisodeMetadata(**metadata_dict)
            
            # Ensure integration is set (if updating legacy episode)
            if episode_metadata.integration != "langgraph":
                # We don't overwrite if it's google_adk, but maybe we should if we are taking over?
                # For now, let's respect existing, or maybe just log.
                pass

            # 3. Create ToolExecution from step
            tool_exec = ToolExecution(
                tool_name=step.get("tool_name", "unknown"),
                success=step.get("success", False),
                duration_ms=step.get("duration_ms", 0),
                timestamp=datetime.utcnow().isoformat(),
                input_params=step.get("input_data", {}) if isinstance(step.get("input_data"), dict) else {"input": str(step.get("input_data"))},
                output_summary=str(step.get("output_data", ""))[:1000], # Truncate for summary
                error=step.get("error")
            )

            # 4. Append to latest run
            latest_run = episode_metadata.get_latest_run(session_id)
            if not latest_run:
                # Should have been created above, but if not:
                run_id = f"run_{int(datetime.utcnow().timestamp())}"
                latest_run = QueryRun(
                    run_id=run_id,
                    user_id=user_id,
                    timestamp=datetime.utcnow().isoformat(),
                    query="LangGraph Session Continued",
                    agent_response="",
                    tools_used=[]
                )
                episode_metadata.add_query_run(session_id, latest_run)
            
            latest_run.tools_used.append(tool_exec)
            
            # 5. Update episode metadata
            self.ryumem.update_episode_metadata(episode.uuid, episode_metadata.model_dump())
            
        except Exception as e:
            logger.error(f"Failed to save step to Ryumem: {e}")

    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load session history from Ryumem.
        
        Returns a list of steps (ToolExecutions) for the session.
        """
        try:
            episode = self.ryumem.get_episode_by_session_id(session_id)
            if not episode:
                return []
            
            metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else {}
            if isinstance(metadata_dict, str):
                metadata_dict = json.loads(metadata_dict)
                
            episode_metadata = EpisodeMetadata(**metadata_dict)
            
            # Collect all tool executions for this session
            steps = []
            if session_id in episode_metadata.sessions:
                for run in episode_metadata.sessions[session_id]:
                    for tool in run.tools_used:
                        steps.append({
                            "tool_name": tool.tool_name,
                            "input_data": tool.input_params,
                            "output_data": tool.output_summary, # We only have summary in metadata
                            "success": tool.success,
                            "error": tool.error,
                            "duration_ms": tool.duration_ms,
                            "timestamp": tool.timestamp
                        })
            return steps
            
        except Exception as e:
            logger.error(f"Failed to load session from Ryumem: {e}")
            return []
