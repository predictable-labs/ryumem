"""
Workflow storage operations for vector DB.

Handles CRUD operations for workflows in the Ryugraph database.
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.utils.embeddings import EmbeddingClient
from ryumem_server.workflows.models import WorkflowDefinition

logger = logging.getLogger(__name__)


class WorkflowStorage:
    """Manages workflow storage in the graph database."""

    def __init__(self, db: RyugraphDB, embedding_client: EmbeddingClient):
        """
        Initialize workflow storage.

        Args:
            db: Graph database instance
            embedding_client: Client for generating embeddings
        """
        self.db = db
        self.embedding_client = embedding_client

    def save_workflow(self, workflow: WorkflowDefinition) -> str:
        """
        Save a workflow to the database.

        Args:
            workflow: Workflow definition to save

        Returns:
            UUID of the saved workflow
        """
        # Generate embedding for workflow description
        description_embedding = self.embedding_client.get_embedding(workflow.description)

        # Serialize nodes to JSON
        nodes_json = json.dumps([node.model_dump() for node in workflow.nodes])

        # Insert workflow node
        query = """
        CREATE (w:Workflow {
            uuid: $uuid,
            name: $name,
            description: $description,
            query_template: $query_template,
            description_embedding: $description_embedding,
            nodes_json: $nodes_json,
            success_count: $success_count,
            failure_count: $failure_count,
            created_at: $created_at,
            updated_at: $updated_at,
            user_id: $user_id
        })
        """

        self.db.execute(
            query,
            {
                "uuid": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "query_template": workflow.query_template,
                "description_embedding": description_embedding,
                "nodes_json": nodes_json,
                "success_count": workflow.success_count,
                "failure_count": workflow.failure_count,
                "created_at": workflow.created_at,
                "updated_at": workflow.updated_at,
                "user_id": workflow.user_id,
            },
        )

        logger.info(f"Saved workflow {workflow.workflow_id}: {workflow.name}")
        return workflow.workflow_id

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """
        Retrieve a workflow by ID.

        Args:
            workflow_id: UUID of the workflow

        Returns:
            WorkflowDefinition or None if not found
        """
        query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        RETURN w.uuid, w.name, w.description, w.query_template,
               w.nodes_json, w.success_count, w.failure_count,
               w.created_at, w.updated_at, w.user_id
        """

        results = self.db.execute(query, {"workflow_id": workflow_id})

        if not results:
            return None

        row = results[0]
        nodes = json.loads(row["w.nodes_json"])

        return WorkflowDefinition(
            workflow_id=row["w.uuid"],
            name=row["w.name"],
            description=row["w.description"],
            query_template=row["w.query_template"],
            nodes=nodes,
            success_count=row["w.success_count"],
            failure_count=row["w.failure_count"],
            created_at=row["w.created_at"],
            updated_at=row["w.updated_at"],
            user_id=row["w.user_id"],
        )

    def search_similar_workflows(
        self, query_embedding: List[float], threshold: float = 0.7, limit: int = 5,
        user_id: Optional[str] = None
    ) -> List[Tuple[WorkflowDefinition, float]]:
        """
        Search for workflows similar to a query.

        Args:
            query_embedding: Embedding vector of the query
            threshold: Minimum similarity score (0-1)
            limit: Maximum number of results
            user_id: Optional user ID filter

        Returns:
            List of (WorkflowDefinition, similarity_score) tuples
        """
        user_filter = "AND w.user_id = $user_id" if user_id else ""

        query = f"""
        MATCH (w:Workflow)
        WHERE array_cosine_similarity(w.description_embedding, $embedding) >= $threshold
        {user_filter}
        RETURN w.uuid, w.name, w.description, w.query_template,
               w.nodes_json, w.success_count, w.failure_count,
               w.created_at, w.updated_at, w.user_id,
               array_cosine_similarity(w.description_embedding, $embedding) AS similarity
        ORDER BY similarity DESC
        LIMIT $limit
        """

        params = {
            "embedding": query_embedding,
            "threshold": threshold,
            "limit": limit,
        }
        if user_id:
            params["user_id"] = user_id

        results = self.db.execute(query, params)

        workflows = []
        for row in results:
            nodes = json.loads(row["w.nodes_json"])
            workflow = WorkflowDefinition(
                workflow_id=row["w.uuid"],
                name=row["w.name"],
                description=row["w.description"],
                query_template=row["w.query_template"],
                nodes=nodes,
                success_count=row["w.success_count"],
                failure_count=row["w.failure_count"],
                created_at=row["w.created_at"],
                updated_at=row["w.updated_at"],
                user_id=row["w.user_id"],
            )
            workflows.append((workflow, row["similarity"]))

        logger.info(f"Found {len(workflows)} similar workflows (threshold={threshold})")
        return workflows

    def increment_success_count(self, workflow_id: str) -> None:
        """
        Increment the success count for a workflow.

        Args:
            workflow_id: UUID of the workflow
        """
        query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        SET w.success_count = w.success_count + 1,
            w.updated_at = $updated_at
        """

        self.db.execute(
            query,
            {"workflow_id": workflow_id, "updated_at": datetime.utcnow()},
        )

        logger.info(f"Incremented success count for workflow {workflow_id}")

    def increment_failure_count(self, workflow_id: str) -> None:
        """
        Increment the failure count for a workflow.

        Args:
            workflow_id: UUID of the workflow
        """
        query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        SET w.failure_count = w.failure_count + 1,
            w.updated_at = $updated_at
        """

        self.db.execute(
            query,
            {"workflow_id": workflow_id, "updated_at": datetime.utcnow()},
        )

        logger.info(f"Incremented failure count for workflow {workflow_id}")

    def list_workflows(
        self, user_id: Optional[str] = None, limit: int = 100
    ) -> List[WorkflowDefinition]:
        """
        List all workflows.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of workflows to return

        Returns:
            List of WorkflowDefinition objects
        """
        user_filter = "WHERE w.user_id = $user_id" if user_id else ""

        query = f"""
        MATCH (w:Workflow)
        {user_filter}
        RETURN w.uuid, w.name, w.description, w.query_template,
               w.nodes_json, w.success_count, w.failure_count,
               w.created_at, w.updated_at, w.user_id
        ORDER BY w.created_at DESC
        LIMIT $limit
        """

        params = {"limit": limit}
        if user_id:
            params["user_id"] = user_id

        results = self.db.execute(query, params)

        workflows = []
        for row in results:
            nodes = json.loads(row["w.nodes_json"])
            workflow = WorkflowDefinition(
                workflow_id=row["w.uuid"],
                name=row["w.name"],
                description=row["w.description"],
                query_template=row["w.query_template"],
                nodes=nodes,
                success_count=row["w.success_count"],
                failure_count=row["w.failure_count"],
                created_at=row["w.created_at"],
                updated_at=row["w.updated_at"],
                user_id=row["w.user_id"],
            )
            workflows.append(workflow)

        return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow.

        Args:
            workflow_id: UUID of the workflow to delete

        Returns:
            True if deleted, False if not found
        """
        query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        DELETE w
        """

        results = self.db.execute(query, {"workflow_id": workflow_id})

        logger.info(f"Deleted workflow {workflow_id}")
        return True
