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
from ryumem.core.workflow_models import WorkflowDefinition

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

    @staticmethod
    def _sanitize_user_id(user_id) -> Optional[str]:
        """
        Convert NaN user_id values from database to None.

        Database null values sometimes become float NaN in results.
        """
        if isinstance(user_id, float) and user_id != user_id:  # Check for NaN
            return None
        return user_id

    def _build_workflow_from_row(self, row: dict, workflow_id: str) -> WorkflowDefinition:
        """
        Build a WorkflowDefinition from a database row.

        Args:
            row: Database row containing workflow data
            workflow_id: UUID of the workflow

        Returns:
            WorkflowDefinition object
        """
        nodes = json.loads(row["w.nodes_json"])

        # Get query templates from Episode nodes
        query_templates_query = """
        MATCH (e:Episode {kind: 'workflow_trigger'})
        WHERE e.metadata CONTAINS $workflow_id
        RETURN e.content
        """

        template_results = self.db.execute(query_templates_query, {"workflow_id": workflow_id})
        query_templates = [r["e.content"] for r in template_results]

        return WorkflowDefinition(
            workflow_id=workflow_id,
            name=row["w.name"],
            description=row["w.description"],
            query_templates=query_templates,
            nodes=nodes,
            success_count=row["w.success_count"],
            failure_count=row["w.failure_count"],
            created_at=row["w.created_at"],
            updated_at=row["w.updated_at"],
            user_id=self._sanitize_user_id(row["w.user_id"]),
        )

    def save_workflow(self, workflow: WorkflowDefinition) -> str:
        """
        Save a workflow to the database.

        Creates a Workflow node for the definition and Episode nodes for each query template.

        Args:
            workflow: Workflow definition to save

        Returns:
            UUID of the saved workflow
        """
        from uuid import uuid4

        # Serialize nodes to JSON
        nodes_json = json.dumps([node.model_dump() for node in workflow.nodes])

        # Use MERGE to create or update workflow node
        workflow_query = """
        MERGE (w:Workflow {uuid: $uuid})
        ON CREATE SET
            w.name = $name,
            w.description = $description,
            w.nodes_json = $nodes_json,
            w.success_count = $success_count,
            w.failure_count = $failure_count,
            w.created_at = $created_at,
            w.updated_at = $updated_at,
            w.user_id = $user_id
        ON MATCH SET
            w.name = $name,
            w.description = $description,
            w.nodes_json = $nodes_json,
            w.updated_at = $updated_at,
            w.user_id = $user_id
        """

        self.db.execute(
            workflow_query,
            {
                "uuid": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "nodes_json": nodes_json,
                "success_count": workflow.success_count,
                "failure_count": workflow.failure_count,
                "created_at": workflow.created_at,
                "updated_at": workflow.updated_at,
                "user_id": workflow.user_id,
            },
        )

        # Delete old Episode trigger nodes for this workflow (if updating)
        delete_query = """
        MATCH (e:Episode {kind: 'workflow_trigger'})
        WHERE e.metadata CONTAINS $workflow_id
        DELETE e
        """
        self.db.execute(delete_query, {"workflow_id": workflow.workflow_id})

        # Create an Episode node for each query template (for vector + BM25 search)
        for query_template in workflow.query_templates:
            query_embedding = self.embedding_client.embed(query_template)

            metadata = json.dumps({
                "workflow_id": workflow.workflow_id,
                "workflow_name": workflow.name,
            })

            episode_query = """
            CREATE (e:Episode {
                uuid: $uuid,
                name: $name,
                content: $content,
                content_embedding: $content_embedding,
                source: $source,
                source_description: $source_description,
                kind: $kind,
                created_at: $created_at,
                valid_at: $valid_at,
                user_id: $user_id,
                agent_id: $agent_id,
                metadata: $metadata,
                entity_edges: $entity_edges
            })
            """

            self.db.execute(
                episode_query,
                {
                    "uuid": str(uuid4()),
                    "name": f"Workflow Trigger: {workflow.name}",
                    "content": query_template,
                    "content_embedding": query_embedding,
                    "source": "workflow",
                    "source_description": f"Trigger query for workflow: {workflow.name}",
                    "kind": "workflow_trigger",
                    "created_at": workflow.created_at,
                    "valid_at": workflow.created_at,
                    "user_id": workflow.user_id,
                    "agent_id": None,
                    "metadata": metadata,
                    "entity_edges": [],
                },
            )

        logger.info(f"Saved workflow {workflow.workflow_id}: {workflow.name} with {len(workflow.query_templates)} trigger queries")
        return workflow.workflow_id

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """
        Retrieve a workflow by ID.

        Args:
            workflow_id: UUID of the workflow

        Returns:
            WorkflowDefinition or None if not found
        """
        # Get workflow definition
        workflow_query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        RETURN w.uuid, w.name, w.description,
               w.nodes_json, w.success_count, w.failure_count,
               w.created_at, w.updated_at, w.user_id
        """

        workflow_results = self.db.execute(workflow_query, {"workflow_id": workflow_id})

        if not workflow_results:
            return None

        row = workflow_results[0]
        return self._build_workflow_from_row(row, workflow_id)

    def search_similar_workflows(
        self, query: str, query_embedding: List[float], threshold: float = 0.7, limit: int = 5,
        user_id: Optional[str] = None
    ) -> List[Tuple[WorkflowDefinition, float]]:
        """
        Search for workflows similar to a query using hybrid search (BM25 + vector).

        Args:
            query: Query text for BM25 search
            query_embedding: Embedding vector for semantic search
            threshold: Minimum RRF score (0-1)
            limit: Maximum number of results
            user_id: Optional user ID filter

        Returns:
            List of (WorkflowDefinition, rrf_score) tuples
        """
        user_filter = "AND e.user_id = $user_id" if user_id else ""

        # Semantic search on Episode nodes with kind='workflow_trigger'
        # BM25 not available in Ryugraph, using semantic search only
        search_query = f"""
        MATCH (e:Episode {{kind: 'workflow_trigger'}})
        WHERE array_cosine_similarity(e.content_embedding, $embedding) >= $threshold
        {user_filter}
        WITH e,
             array_cosine_similarity(e.content_embedding, $embedding) AS similarity_score
        RETURN e.metadata, similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """

        params = {
            "query": query,
            "embedding": query_embedding,
            "threshold": threshold,
            "limit": limit * 3,  # Get more to handle multiple templates per workflow
        }
        if user_id:
            params["user_id"] = user_id

        results = self.db.execute(search_query, params)

        # Group by workflow_id and get the best score for each
        workflow_scores = {}
        for row in results:
            metadata = json.loads(row["e.metadata"])
            workflow_id = metadata.get("workflow_id")
            if not workflow_id:
                continue

            score = row["similarity_score"]
            if workflow_id not in workflow_scores or score > workflow_scores[workflow_id]:
                workflow_scores[workflow_id] = score

        # Retrieve full workflow definitions
        workflows = []
        for workflow_id, score in sorted(workflow_scores.items(), key=lambda x: x[1], reverse=True)[:limit]:
            workflow = self.get_workflow(workflow_id)
            if workflow:
                workflows.append((workflow, score))

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
        RETURN w.uuid, w.name, w.description,
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
            workflow_id = row["w.uuid"]
            workflow = self._build_workflow_from_row(row, workflow_id)
            workflows.append(workflow)

        return workflows

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow and its trigger query Episodes.

        Args:
            workflow_id: UUID of the workflow to delete

        Returns:
            True if deleted, False if not found
        """
        # Delete workflow node
        workflow_query = """
        MATCH (w:Workflow {uuid: $workflow_id})
        DELETE w
        """
        self.db.execute(workflow_query, {"workflow_id": workflow_id})

        # Delete associated Episode trigger nodes
        episode_query = """
        MATCH (e:Episode {kind: 'workflow_trigger'})
        WHERE e.metadata CONTAINS $workflow_id
        DELETE e
        """
        self.db.execute(episode_query, {"workflow_id": workflow_id})

        logger.info(f"Deleted workflow {workflow_id} and its trigger queries")
        return True
