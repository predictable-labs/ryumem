"""
Session management integrated with episode metadata.

Manages session state through the existing episode metadata structure.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ryumem.core.metadata_models import EpisodeMetadata
from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.models import EpisodeNode, EpisodeKind, EpisodeType
from ryumem_server.sessions.models import SessionRun, SessionStatus

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state through episode metadata."""

    def __init__(self, db: RyugraphDB):
        """
        Initialize session manager.

        Args:
            db: Graph database instance
        """
        self.db = db

    def get_or_create_session_episode(
        self, session_id: str, user_id: str
    ) -> EpisodeNode:
        """
        Get existing episode for session or create a new one.

        Args:
            session_id: Session ID
            user_id: User ID

        Returns:
            EpisodeNode containing the session
        """
        # Try to find existing episode for this session
        episode = self.db.get_episode_by_session_id(session_id)

        if episode:
            return episode

        # Create new episode for this session
        metadata = EpisodeMetadata(integration="google_adk")
        metadata.sessions[session_id] = {
            "status": SessionStatus.ACTIVE.value,
            "workflow_id": None,
            "session_variables": {},
            "current_node": None,
            "runs": [],
        }

        episode = EpisodeNode(
            name=f"Session {session_id}",
            content=f"Session created for user {user_id}",
            source=EpisodeType.message,
            kind=EpisodeKind.query,
            user_id=user_id,
            metadata=metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict(),
        )

        # Save to DB
        self.db.add_episode(episode)
        logger.info(f"Created new episode for session {session_id}")

        return episode

    def get_session(self, session_id: str) -> Optional[SessionRun]:
        """
        Retrieve session state.

        Args:
            session_id: Session ID

        Returns:
            SessionRun or None if not found
        """
        episode = self.db.get_episode_by_session_id(session_id)
        if not episode:
            return None

        # Parse metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        session_data = metadata.sessions.get(session_id)
        if not session_data:
            return None

        # Convert to SessionRun
        return SessionRun(
            session_id=session_id,
            user_id=episode.user_id or "",
            status=SessionStatus(session_data.get("status", "active")),
            workflow_id=session_data.get("workflow_id"),
            session_variables=session_data.get("session_variables", {}),
            started_at=episode.created_at,
            updated_at=episode.created_at,  # TODO: track actual update time
            current_node=session_data.get("current_node"),
            error=session_data.get("error"),
        )

    def update_session_variables(
        self, session_id: str, user_id: str, variables: Dict[str, Any]
    ) -> None:
        """
        Update session variables.

        Args:
            session_id: Session ID
            user_id: User ID
            variables: Variables to merge
        """
        episode = self.get_or_create_session_episode(session_id, user_id)

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        if session_id not in metadata.sessions:
            metadata.sessions[session_id] = {
                "status": "active",
                "workflow_id": None,
                "session_variables": {},
                "current_node": None,
                "runs": [],
            }

        metadata.sessions[session_id]["session_variables"].update(variables)

        # Save back to episode
        self.db.update_episode_metadata(
            episode.uuid,
            metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        )

        logger.debug(f"Updated variables for session {session_id}")

    def set_session_status(
        self, session_id: str, user_id: str, status: SessionStatus, error: Optional[str] = None
    ) -> None:
        """
        Update session status.

        Args:
            session_id: Session ID
            user_id: User ID
            status: New status
            error: Optional error message
        """
        episode = self.get_or_create_session_episode(session_id, user_id)

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        if session_id in metadata.sessions:
            metadata.sessions[session_id]["status"] = status.value
            if error:
                metadata.sessions[session_id]["error"] = error

            # Save back to episode
            self.db.update_episode_metadata(
                episode.uuid,
                metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
            )

            logger.info(f"Set session {session_id} status to {status}")

    def set_current_node(self, session_id: str, user_id: str, node_id: Optional[str]) -> None:
        """
        Set currently executing node.

        Args:
            session_id: Session ID
            user_id: User ID
            node_id: Node ID or None
        """
        episode = self.get_or_create_session_episode(session_id, user_id)

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        if session_id in metadata.sessions:
            metadata.sessions[session_id]["current_node"] = node_id

            # Save back to episode
            self.db.update_episode_metadata(
                episode.uuid,
                metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
            )

    def set_workflow_id(self, session_id: str, user_id: str, workflow_id: str) -> None:
        """
        Set workflow ID for session.

        Args:
            session_id: Session ID
            user_id: User ID
            workflow_id: Workflow ID
        """
        episode = self.get_or_create_session_episode(session_id, user_id)

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        if session_id in metadata.sessions:
            metadata.sessions[session_id]["workflow_id"] = workflow_id

            # Save back to episode
            self.db.update_episode_metadata(
                episode.uuid,
                metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
            )

    def get_active_sessions(self, user_id: Optional[str] = None) -> List[SessionRun]:
        """
        Get all active sessions.

        Args:
            user_id: Optional user ID filter

        Returns:
            List of active SessionRun objects
        """
        # Query all episodes with metadata
        query = """
        MATCH (e:Episode)
        WHERE e.metadata IS NOT NULL
        """
        if user_id:
            query += " AND e.user_id = $user_id"

        query += """
        RETURN e.uuid, e.user_id, e.created_at, e.metadata
        """

        params = {"user_id": user_id} if user_id else {}
        results = self.db.execute(query, params)

        active_sessions = []
        for row in results:
            try:
                metadata_dict = row["e.metadata"] if isinstance(row["e.metadata"], dict) else json.loads(row["e.metadata"])
                metadata = EpisodeMetadata(**metadata_dict)

                for session_id, session_data in metadata.sessions.items():
                    if session_data.get("status") == "active":
                        active_sessions.append(
                            SessionRun(
                                session_id=session_id,
                                user_id=row["e.user_id"] or "",
                                status=SessionStatus.ACTIVE,
                                workflow_id=session_data.get("workflow_id"),
                                session_variables=session_data.get("session_variables", {}),
                                started_at=row["e.created_at"],
                                updated_at=row["e.created_at"],
                                current_node=session_data.get("current_node"),
                            )
                        )
            except Exception as e:
                logger.warning(f"Error parsing episode metadata: {e}")
                continue

        logger.debug(f"Found {len(active_sessions)} active sessions")
        return active_sessions

    def list_sessions(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> List[SessionRun]:
        """
        List all sessions.

        Args:
            user_id: Optional user ID filter
            limit: Maximum results

        Returns:
            List of SessionRun objects
        """
        # Similar to get_active_sessions but without status filter
        query = """
        MATCH (e:Episode)
        WHERE e.metadata IS NOT NULL
        """
        if user_id:
            query += " AND e.user_id = $user_id"

        query += """
        RETURN e.uuid, e.user_id, e.created_at, e.metadata
        ORDER BY e.created_at DESC
        LIMIT $limit
        """

        params = {"limit": limit}
        if user_id:
            params["user_id"] = user_id

        results = self.db.execute(query, params)

        all_sessions = []
        for row in results:
            try:
                metadata_dict = row["e.metadata"] if isinstance(row["e.metadata"], dict) else json.loads(row["e.metadata"])
                metadata = EpisodeMetadata(**metadata_dict)

                for session_id, session_data in metadata.sessions.items():
                    all_sessions.append(
                        SessionRun(
                            session_id=session_id,
                            user_id=row["e.user_id"] or "",
                            status=SessionStatus(session_data.get("status", "active")),
                            workflow_id=session_data.get("workflow_id"),
                            session_variables=session_data.get("session_variables", {}),
                            started_at=row["e.created_at"],
                            updated_at=row["e.created_at"],
                            current_node=session_data.get("current_node"),
                            error=session_data.get("error"),
                        )
                    )
            except Exception as e:
                logger.warning(f"Error parsing episode metadata: {e}")
                continue

        return all_sessions

    def add_query_run_to_episode(
        self, episode_id: str, session_id: str, user_id: str, query_run: "QueryRun"
    ) -> None:
        """
        Add a query run to a specific episode (links episode to session).

        Args:
            episode_id: Specific episode ID to update
            session_id: Session ID
            user_id: User ID
            query_run: QueryRun object to add
        """
        episode = self.db.get_episode_by_uuid(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        # Add the query run (links session to this episode)
        metadata.add_query_run(session_id, query_run)

        # Save back to episode
        self.db.update_episode_metadata(
            episode.uuid,
            metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        )

        logger.info(f"Added query run to session {session_id} in episode {episode.uuid[:8]}")

    def add_query_run(
        self, session_id: str, user_id: str, query_run: "QueryRun"
    ) -> None:
        """
        Add a query run to a session (finds or creates episode by session_id).

        Args:
            session_id: Session ID
            user_id: User ID
            query_run: QueryRun object to add
        """
        episode = self.get_or_create_session_episode(session_id, user_id)

        # Parse and update metadata
        metadata_dict = episode.metadata if isinstance(episode.metadata, dict) else json.loads(episode.metadata)
        metadata = EpisodeMetadata(**metadata_dict)

        # Add the query run
        metadata.add_query_run(session_id, query_run)

        # Save back to episode
        self.db.update_episode_metadata(
            episode.uuid,
            metadata.model_dump() if hasattr(metadata, 'model_dump') else metadata.dict()
        )

        logger.info(f"Added query run to session {session_id}")

    def get_session_variables(self, session_id: str) -> Dict[str, Any]:
        """
        Get session variables.

        Args:
            session_id: Session ID

        Returns:
            Session variables dict
        """
        session = self.get_session(session_id)
        if not session:
            return {}
        return session.session_variables
