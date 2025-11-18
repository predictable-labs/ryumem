"""
FastAPI Server for Ryumem - Bi-temporal Knowledge Graph Memory System

This server provides RESTful API endpoints for:
- Adding episodes (memories)
- Searching/querying the knowledge graph
- Getting entity context
- Managing communities and memory pruning

Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ryumem import Ryumem
from ryumem.core.config import RyumemConfig
from ryumem.core.metadata_models import EpisodeMetadata, QueryRun, ToolExecution

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Dependency injection for per-request Ryumem instances
def get_ryumem():
    """
    Create a new Ryumem instance per request with automatic connection cleanup.

    This ensures:
    - Database connections are only opened when API requests arrive
    - Connections are automatically closed after the request completes
    - READ_ONLY mode is maintained for safe concurrent access
    - No persistent connections that could leak resources
    """
    # Load config from environment
    config = RyumemConfig()

    # Override read_only to ensure server always uses READ_ONLY mode
    config.database.read_only = True

    # Create new instance with context manager for automatic cleanup
    with Ryumem(config=config) as ryumem:
        yield ryumem
    # Connection automatically closed when request completes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server startup/shutdown lifecycle"""
    logger.info("Starting Ryumem server...")
    logger.info("Using per-request database connections in READ_ONLY mode")
    
    # Print configuration on startup
    config = RyumemConfig()
    config.database.read_only = True

    yield

    logger.info("Shutting down Ryumem server...")
    logger.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Ryumem API",
    description="RESTful API for Ryumem - Bi-temporal Knowledge Graph Memory System",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Request/Response Models =====

class AddEpisodeRequest(BaseModel):
    """Request model for adding an episode"""
    content: str = Field(..., description="Episode content (text, message, or JSON)")
    user_id: str = Field(..., description="User ID for isolation")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    source: str = Field("text", description="Episode source type: text, message, or json")
    metadata: Optional[Dict] = Field(None, description="Optional metadata")
    extract_entities: Optional[bool] = Field(None, description="Override config setting for entity extraction (None uses config default)")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Alice works at Google as a Software Engineer in Mountain View.",
                "user_id": "user_123",
                "source": "text",
                "extract_entities": False
            }
        }


class AddEpisodeResponse(BaseModel):
    """Response model for adding an episode"""
    episode_id: str = Field(..., description="UUID of the created episode")
    message: str = Field(..., description="Success message")
    timestamp: str = Field(..., description="Timestamp of creation")


class EpisodeInfo(BaseModel):
    """Episode information"""
    uuid: str
    name: str
    content: str
    source: str
    source_description: str
    created_at: str
    valid_at: str
    user_id: Optional[str] = None
    metadata: Optional[str] = None


class GetEpisodesResponse(BaseModel):
    """Response model for getting episodes"""
    episodes: List[EpisodeInfo] = Field(default_factory=list, description="List of episodes")
    total: int = Field(0, description="Total count of episodes")
    offset: int = Field(0, description="Offset for pagination")
    limit: int = Field(20, description="Limit for pagination")


class SearchRequest(BaseModel):
    """Request model for searching"""
    query: str = Field(..., description="Search query text")
    user_id: str = Field(..., description="User ID to search within")
    limit: int = Field(10, description="Maximum number of results", ge=1, le=100)
    strategy: str = Field("hybrid", description="Search strategy: semantic, bm25, traversal, or hybrid")
    min_rrf_score: Optional[float] = Field(None, description="Minimum RRF score for hybrid search")
    min_bm25_score: Optional[float] = Field(None, description="Minimum BM25 score")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Where does Alice work?",
                "user_id": "user_123",
                "limit": 10,
                "strategy": "hybrid"
            }
        }


class EntityInfo(BaseModel):
    """Entity information"""
    uuid: str
    name: str
    entity_type: str
    summary: str
    mentions: int
    score: float = 0.0


class EdgeInfo(BaseModel):
    """Edge/relationship information"""
    uuid: str
    source_uuid: str  # Added for graph visualization
    target_uuid: str  # Added for graph visualization
    source_name: str
    target_name: str
    relation_type: str
    fact: str
    mentions: int
    score: float = 0.0


class SearchResponse(BaseModel):
    """Response model for search"""
    entities: List[EntityInfo] = Field(default_factory=list, description="List of entities found")
    edges: List[EdgeInfo] = Field(default_factory=list, description="List of relationships found")
    query: str = Field(..., description="Original query")
    strategy: str = Field(..., description="Search strategy used")
    count: int = Field(..., description="Total number of results")


class EntityContextResponse(BaseModel):
    """Response model for entity context"""
    entity: Optional[EntityInfo] = Field(None, description="Entity information")
    relationships: List[EdgeInfo] = Field(default_factory=list, description="Related edges")
    relationship_count: int = Field(0, description="Total relationship count")
    message: Optional[str] = Field(None, description="Error or status message")


class StatsResponse(BaseModel):
    """Response model for system stats"""
    total_episodes: int = Field(0, description="Total number of episodes")
    total_entities: int = Field(0, description="Total number of entities")
    total_relationships: int = Field(0, description="Total number of relationships")
    total_communities: int = Field(0, description="Total number of communities")
    db_path: str = Field(..., description="Database path")


class UpdateCommunitiesRequest(BaseModel):
    """Request model for updating communities"""
    resolution: float = Field(1.0, description="Resolution parameter for Louvain algorithm", ge=0.1, le=5.0)
    min_community_size: int = Field(2, description="Minimum number of entities per community", ge=1)


class UpdateCommunitiesResponse(BaseModel):
    """Response model for updating communities"""
    num_communities: int = Field(..., description="Number of communities created")
    message: str = Field(..., description="Success message")


class PruneMemoriesRequest(BaseModel):
    """Request model for pruning memories"""
    user_id: str = Field(..., description="User ID to prune")
    expired_cutoff_days: int = Field(90, description="Delete expired edges older than N days", ge=1)
    min_mentions: int = Field(2, description="Minimum mentions for entities to keep", ge=1)
    min_age_days: int = Field(30, description="Minimum age before pruning low-mention entities", ge=1)
    compact_redundant: bool = Field(True, description="Whether to merge redundant edges")


class PruneMemoriesResponse(BaseModel):
    """Response model for pruning memories"""
    expired_edges_deleted: int = Field(0, description="Number of expired edges deleted")
    entities_deleted: int = Field(0, description="Number of entities deleted")
    edges_merged: int = Field(0, description="Number of edges merged")
    message: str = Field(..., description="Success message")


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    ryumem_initialized: bool = Field(..., description="Whether Ryumem is initialized")
    timestamp: str = Field(..., description="Current timestamp")


class GraphNode(BaseModel):
    """Node in the knowledge graph"""
    uuid: str = Field(..., description="Node UUID")
    name: str = Field(..., description="Entity name")
    type: str = Field(..., description="Entity type")
    summary: str = Field(..., description="Entity summary")
    mentions: int = Field(..., description="Number of mentions")
    user_id: Optional[str] = Field(None, description="User ID")


class GraphEdge(BaseModel):
    """Edge in the knowledge graph"""
    uuid: str = Field(..., description="Edge UUID")
    source: str = Field(..., description="Source node UUID")
    target: str = Field(..., description="Target node UUID")
    label: str = Field(..., description="Relation type")
    fact: str = Field(..., description="Relationship fact")
    mentions: int = Field(..., description="Number of mentions")


class GraphCount(BaseModel):
    """Count of graph elements"""
    nodes: int = Field(0, description="Total node count")
    edges: int = Field(0, description="Total edge count")


class GraphDataResponse(BaseModel):
    """Response model for graph data"""
    nodes: List[GraphNode] = Field(default_factory=list, description="List of nodes (entities)")
    edges: List[GraphEdge] = Field(default_factory=list, description="List of edges (relationships)")
    count: GraphCount = Field(default_factory=GraphCount, description="Count of nodes and edges")


class EntitiesListResponse(BaseModel):
    """Response model for entities list"""
    entities: List[EntityInfo] = Field(default_factory=list, description="List of entities")
    total: int = Field(0, description="Total count of entities")
    offset: int = Field(0, description="Offset for pagination")
    limit: int = Field(50, description="Limit for pagination")


class RelationshipsListResponse(BaseModel):
    """Response model for relationships list"""
    relationships: List[EdgeInfo] = Field(default_factory=list, description="List of relationships")
    total: int = Field(0, description="Total count of relationships")
    offset: int = Field(0, description="Offset for pagination")
    limit: int = Field(50, description="Limit for pagination")


class EntityTypesResponse(BaseModel):
    """Response model for entity types"""
    entity_types: List[str] = Field(default_factory=list, description="List of unique entity types")


# ===== API Endpoints =====

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        ryumem_initialized=True,  # Always true since we use per-request instances
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        ryumem_initialized=True,  # Always true since we use per-request instances
        timestamp=datetime.now().isoformat()
    )


@app.get("/users")
async def get_users(ryumem: Ryumem = Depends(get_ryumem)):
    """
    Get all distinct user IDs in the database.

    Returns:
        List of user_id strings
    """
    try:
        users = ryumem.db.get_all_users()
        return {"users": users}
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/episodes", response_model=AddEpisodeResponse)
async def add_episode(
    request: AddEpisodeRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Add a new episode to the memory system.

    This will:
    1. Create an episode node
    2. Extract entities and relationships
    3. Update the knowledge graph
    4. Detect and handle contradictions

    Note: This endpoint will fail in READ_ONLY mode.
    Use a separate write instance for adding episodes.
    """
    try:
        episode_id = ryumem.add_episode(
            content=request.content,
            user_id=request.user_id,
            session_id=request.session_id,
            source=request.source,
            metadata=request.metadata,
            extract_entities=request.extract_entities,
        )

        return AddEpisodeResponse(
            episode_id=episode_id,
            message="Episode added successfully",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error adding episode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error adding episode: {str(e)}")


@app.get("/episodes", response_model=GetEpisodesResponse)
async def get_episodes(
    user_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    sort_order: str = "desc",
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get episodes with pagination and filtering.

    Supports:
    - Pagination (limit, offset)
    - Date range filtering (start_date, end_date)
    - Content search
    - Sort order (newest/oldest first)
    """
    try:
        # Parse dates if provided
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid start_date format: {start_date}")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid end_date format: {end_date}")

        # Get episodes from database
        result = ryumem.db.get_episodes(
            user_id=user_id,
            limit=limit,
            offset=offset,
            start_date=start_dt,
            end_date=end_dt,
            search=search,
            sort_order=sort_order,
        )

        # Convert to response format
        # Helper to convert nan/None to proper None
        def clean_value(val):
            if val is None:
                return None
            if isinstance(val, float):
                import math
                if math.isnan(val):
                    return None
            return val

        episodes = []
        for ep in result["episodes"]:
            episodes.append(EpisodeInfo(
                uuid=ep["uuid"],
                name=ep["name"],
                content=ep["content"],
                source=ep["source"],
                source_description=ep["source_description"],
                created_at=ep["created_at"].isoformat() if isinstance(ep["created_at"], datetime) else str(ep["created_at"]),
                valid_at=ep["valid_at"].isoformat() if isinstance(ep["valid_at"], datetime) else str(ep["valid_at"]),
                user_id=clean_value(ep.get("user_id")),
                metadata=clean_value(ep.get("metadata")),
            ))

        return GetEpisodesResponse(
            episodes=episodes,
            total=result["total"],
            offset=offset,
            limit=limit
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episodes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting episodes: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Search the knowledge graph.

    Supports multiple strategies:
    - semantic: Embedding-based similarity search
    - bm25: Keyword-based search
    - traversal: Graph-based navigation
    - hybrid: Combines all strategies (recommended)
    """
    try:
        results = ryumem.search(
            query=request.query,
            user_id=request.user_id,
            limit=request.limit,
            strategy=request.strategy,
            min_rrf_score=request.min_rrf_score,
            min_bm25_score=request.min_bm25_score,
        )
        
        # Convert entities to response format
        entities = []
        for entity in results.entities:
            entities.append(EntityInfo(
                uuid=entity.uuid,
                name=entity.name,
                entity_type=entity.entity_type,
                summary=entity.summary or "",
                mentions=entity.mentions,
                score=results.scores.get(entity.uuid, 0.0)
            ))
        
        # Convert edges to response format
        edges = []
        for edge in results.edges:
            # Get entity names from the graph if available
            source_name = ""
            target_name = ""
            
            # Find source and target entities in results
            for entity in results.entities:
                if entity.uuid == edge.source_node_uuid:
                    source_name = entity.name
                if entity.uuid == edge.target_node_uuid:
                    target_name = entity.name
            
            edges.append(EdgeInfo(
                uuid=edge.uuid,
                source_uuid=edge.source_node_uuid,
                target_uuid=edge.target_node_uuid,
                source_name=source_name,
                target_name=target_name,
                relation_type=edge.name,
                fact=edge.fact,
                mentions=edge.mentions,
                score=results.scores.get(edge.uuid, 0.0)
            ))
        
        return SearchResponse(
            entities=entities,
            edges=edges,
            query=request.query,
            strategy=request.strategy,
            count=len(entities) + len(edges)
        )
    except Exception as e:
        logger.error(f"Error searching: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching: {str(e)}")


@app.get("/entity/{entity_name}", response_model=EntityContextResponse)
async def get_entity_context(
    entity_name: str,
    user_id: str,
    max_depth: int = 2,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get comprehensive context for an entity by name.

    Returns:
    - Entity details
    - All relationships
    - Related entities
    """
    if not ryumem:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")

    try:
        context = ryumem.get_entity_context(
            entity_name=entity_name,
            user_id=user_id,
            max_depth=max_depth,
        )
        
        if not context:
            return EntityContextResponse(
                message=f"Entity '{entity_name}' not found"
            )
        
        # Convert entity
        entity_data = context.get("entity", {})
        entity_info = None
        if entity_data:
            entity_info = EntityInfo(
                uuid=entity_data.get("uuid", ""),
                name=entity_data.get("name", ""),
                entity_type=entity_data.get("entity_type", ""),
                summary=entity_data.get("summary", ""),
                mentions=entity_data.get("mentions", 0),
                score=1.0
            )
        
        # Convert relationships
        edges = []
        for edge_data in context.get("relationships", []):
            edges.append(EdgeInfo(
                uuid=edge_data.get("uuid", ""),
                source_uuid=edge_data.get("source_uuid", ""),
                target_uuid=edge_data.get("target_uuid", ""),
                source_name=edge_data.get("source_name", ""),
                target_name=edge_data.get("target_name", ""),
                relation_type=edge_data.get("relation_type", ""),
                fact=edge_data.get("fact", ""),
                mentions=edge_data.get("mentions", 0),
                score=0.0
            ))
        
        return EntityContextResponse(
            entity=entity_info,
            relationships=edges,
            relationship_count=context.get("relationship_count", 0),
            message="Entity context retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting entity context: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting entity context: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get global system statistics.

    Returns counts of episodes, entities, relationships, and communities.
    """

    try:
        # Count episodes
        episode_query = """
        MATCH (ep:Episode)
        RETURN COUNT(ep) AS count
        """
        episode_result = ryumem.db.execute(episode_query, {})
        total_episodes = episode_result[0]["count"] if episode_result else 0

        # Count entities
        entity_query = """
        MATCH (e:Entity)
        RETURN COUNT(e) AS count
        """
        entity_result = ryumem.db.execute(entity_query, {})
        total_entities = entity_result[0]["count"] if entity_result else 0

        # Count relationships
        rel_query = """
        MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
        RETURN COUNT(r) AS count
        """
        rel_result = ryumem.db.execute(rel_query, {})
        total_relationships = rel_result[0]["count"] if rel_result else 0

        # Count communities
        comm_query = """
        MATCH (c:Community)
        RETURN COUNT(c) AS count
        """
        comm_result = ryumem.db.execute(comm_query, {})
        total_communities = comm_result[0]["count"] if comm_result else 0

        return StatsResponse(
            total_episodes=total_episodes,
            total_entities=total_entities,
            total_relationships=total_relationships,
            total_communities=total_communities,
            db_path=ryumem.config.database.db_path
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.post("/communities/update", response_model=UpdateCommunitiesResponse)
async def update_communities(
    request: UpdateCommunitiesRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Detect and update communities using Louvain algorithm.

    Communities cluster related entities together for:
    - More efficient retrieval
    - Higher-level reasoning
    - Better organization

    Note: This endpoint will fail in READ_ONLY mode.
    """
    try:
        num_communities = ryumem.update_communities(
            resolution=request.resolution,
            min_community_size=request.min_community_size,
        )
        
        return UpdateCommunitiesResponse(
            num_communities=num_communities,
            message=f"Successfully created {num_communities} communities"
        )
    except Exception as e:
        logger.error(f"Error updating communities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating communities: {str(e)}")


@app.post("/prune", response_model=PruneMemoriesResponse)
async def prune_memories(
    request: PruneMemoriesRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Prune and compact memories to keep the graph efficient.

    This performs:
    - Delete facts that were invalidated/expired long ago
    - Remove entities with very few mentions (likely noise)
    - Merge near-duplicate relationship facts

    Note: This endpoint will fail in READ_ONLY mode.
    """
    try:
        stats = ryumem.prune_memories(
            user_id=request.user_id,
            expired_cutoff_days=request.expired_cutoff_days,
            min_mentions=request.min_mentions,
            min_age_days=request.min_age_days,
            compact_redundant=request.compact_redundant,
        )
        
        return PruneMemoriesResponse(
            expired_edges_deleted=stats.get("expired_edges_deleted", 0),
            entities_deleted=stats.get("entities_deleted", 0),
            edges_merged=stats.get("edges_merged", 0),
            message="Memory pruning completed successfully"
        )
    except Exception as e:
        logger.error(f"Error pruning memories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error pruning memories: {str(e)}")


@app.get("/graph/data", response_model=GraphDataResponse)
async def get_graph_data(
    user_id: Optional[str] = None,
    limit: int = 1000,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get the full knowledge graph structure for visualization.

    Returns all entities (nodes) and relationships (edges) in the knowledge graph.
    """
    try:
        # Get all entities (optionally filtered by user_id)
        if user_id:
            entities_data = ryumem.db.get_all_entities(user_id=user_id)
        else:
            entities_data = ryumem.db.get_all_entities()

        # Apply limit
        entities_data = entities_data[:limit]

        # Get all edges (optionally filtered by user_id)
        if user_id:
            edges_data = ryumem.db.get_all_edges(user_id=user_id)
        else:
            edges_data = ryumem.db.get_all_edges()

        # Apply limit
        edges_data = edges_data[:limit]

        # Convert to graph format
        nodes = []
        for entity in entities_data:
            nodes.append(GraphNode(
                uuid=entity['uuid'],
                name=entity['name'],
                type=entity['entity_type'],
                summary=entity['summary'],
                mentions=entity['mentions'],
                user_id=entity.get('user_id')
            ))

        edges = []
        for edge in edges_data:
            edges.append(GraphEdge(
                uuid=edge['uuid'],
                source=edge['source_uuid'],
                target=edge['target_uuid'],
                label=edge['relation_type'],
                fact=edge['fact'],
                mentions=edge.get('mentions', 1)
            ))

        return GraphDataResponse(
            nodes=nodes,
            edges=edges,
            count=GraphCount(
                nodes=len(nodes),
                edges=len(edges)
            )
        )
    except Exception as e:
        logger.error(f"Error getting graph data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting graph data: {str(e)}")


@app.get("/entities/list", response_model=EntitiesListResponse)
async def list_entities(
    user_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get a paginated list of entities.

    Useful for browsing all entities in the system.
    """
    try:
        # Get all entities (optionally filtered by user_id)
        if user_id:
            all_entities = ryumem.db.get_all_entities(user_id=user_id)
        else:
            all_entities = ryumem.db.get_all_entities()

        # Filter by type if specified
        if entity_type:
            filtered_entities = [e for e in all_entities if e['entity_type'] == entity_type]
        else:
            filtered_entities = all_entities

        total = len(filtered_entities)

        # Apply pagination
        paginated = filtered_entities[offset:offset + limit]

        # Convert to EntityInfo
        entities = []
        for entity in paginated:
            entities.append(EntityInfo(
                uuid=entity['uuid'],
                name=entity['name'],
                entity_type=entity['entity_type'],
                summary=entity['summary'],
                mentions=entity['mentions'],
                score=0.0
            ))

        return EntitiesListResponse(
            entities=entities,
            total=total,
            offset=offset,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing entities: {str(e)}")


@app.get("/entities/types", response_model=EntityTypesResponse)
async def get_entity_types(
    user_id: Optional[str] = None,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get all unique entity types in the database.

    This is useful for populating dropdowns and filters in the UI.
    """
    try:
        # Query database for unique entity types
        if user_id:
            query = "MATCH (e:Entity) WHERE e.user_id = $user_id RETURN DISTINCT e.entity_type ORDER BY e.entity_type"
            result = ryumem.db.conn.execute(query, {"user_id": user_id})
        else:
            query = "MATCH (e:Entity) RETURN DISTINCT e.entity_type ORDER BY e.entity_type"
            result = ryumem.db.conn.execute(query, {})
        if user_id:
            query = "MATCH (e:Entity) WHERE e.user_id = $user_id RETURN DISTINCT e.entity_type ORDER BY e.entity_type"
            result = ryumem.db.conn.execute(query, {"user_id": user_id})
        else:
            query = "MATCH (e:Entity) RETURN DISTINCT e.entity_type ORDER BY e.entity_type"
            result = ryumem.db.conn.execute(query, {})

        entity_types = []
        while result.has_next():
            entity_type = result.get_next()[0]
            if entity_type:  # Skip null types
                entity_types.append(entity_type)

        return EntityTypesResponse(entity_types=entity_types)
    except Exception as e:
        logger.error(f"Error getting entity types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting entity types: {str(e)}")


@app.get("/relationships/list", response_model=RelationshipsListResponse)
async def list_relationships(
    user_id: Optional[str] = None,
    relation_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get a paginated list of relationships.

    Useful for browsing all relationships in the system.
    """
    try:
        # Get all edges from database
        if user_id:
            all_edges = ryumem.db.get_all_edges(user_id=user_id)
            all_entities = ryumem.db.get_all_entities(user_id=user_id)
        else:
            all_edges = ryumem.db.get_all_edges()
            all_entities = ryumem.db.get_all_entities()

        # Create entity UUID to name mapping
        entity_map = {e['uuid']: e['name'] for e in all_entities}

        # Filter edges to only include those with entities in the filtered set
        if user_id:
            entity_uuids = set(entity_map.keys())
            all_edges = [e for e in all_edges if e['source_uuid'] in entity_uuids and e['target_uuid'] in entity_uuids]

        # Filter by relation type if specified
        if relation_type:
            filtered_edges = [e for e in all_edges if e['relation_type'] == relation_type]
        else:
            filtered_edges = all_edges

        total = len(filtered_edges)

        # Apply pagination
        paginated = filtered_edges[offset:offset + limit]

        # Convert to EdgeInfo
        relationships = []
        for edge in paginated:
            source_name = entity_map.get(edge['source_uuid'], "Unknown")
            target_name = entity_map.get(edge['target_uuid'], "Unknown")

            relationships.append(EdgeInfo(
                uuid=edge['uuid'],
                source_uuid=edge['source_uuid'],
                target_uuid=edge['target_uuid'],
                source_name=source_name,
                target_name=target_name,
                relation_type=edge['relation_type'],
                fact=edge['fact'],
                mentions=edge.get('mentions', 1),
                score=0.0
            ))

        return RelationshipsListResponse(
            relationships=relationships,
            total=total,
            offset=offset,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing relationships: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing relationships: {str(e)}")


# ============================================================================
# Agent Instruction Management Endpoints
# ============================================================================

class AgentInstructionRequest(BaseModel):
    """Request model for creating/updating agent instructions"""
    instruction_text: str = Field(..., description="The converted/final instruction text to add to agent prompt")
    agent_type: str = Field("google_adk", description="Type of agent (e.g., google_adk, custom_agent)")
    instruction_type: str = Field("tool_tracking", description="Type of instruction (e.g., tool_tracking, memory_guidance)")
    description: str = Field("", description="User-friendly description of what this instruction does")
    user_id: Optional[str] = Field(None, description="Optional user ID for user-specific instructions")
    original_user_request: Optional[str] = Field(None, description="Original request from user before conversion")

    class Config:
        json_schema_extra = {
            "example": {
                "original_user_request": "Make the agent check past tool usage before selecting tools",
                "instruction_text": "TOOL SELECTION GUIDANCE:\nAlways check memory before selecting tools...",
                "agent_type": "google_adk",
                "instruction_type": "tool_tracking",
                "description": "Custom tool selection guidance for improved performance"
            }
        }


class AgentInstructionResponse(BaseModel):
    """Response model for agent instructions"""
    instruction_id: str = Field(..., description="UUID of the instruction episode")
    instruction_text: str = Field(..., description="The converted/final instruction text")
    name: str = Field(..., description="Name/title of the instruction")
    agent_type: str = Field(..., description="Type of agent")
    instruction_type: str = Field(..., description="Type of instruction")
    version: int = Field(..., description="Version number")
    description: str = Field(..., description="Description of the instruction")
    original_user_request: str = Field("", description="Original request from user")
    converted_instruction: str = Field("", description="Converted/final instruction")
    created_at: str = Field(..., description="Creation timestamp")


@app.post("/agent-instructions", response_model=AgentInstructionResponse, tags=["Agent Instructions"])
async def create_agent_instruction(
    request: AgentInstructionRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Create a new custom agent instruction.

    The instruction will be stored in the database and can be retrieved
    by agents to customize their behavior.

    Note: This endpoint will fail in READ_ONLY mode.
    """
    try:
        logger.warning("Server is in read-only mode - agent instruction creation may fail")

        # Save the instruction
        instruction_id = ryumem.save_agent_instruction(
            instruction_text=request.instruction_text,
            agent_type=request.agent_type,
            instruction_type=request.instruction_type,
            description=request.description,
            user_id=request.user_id,
            original_user_request=request.original_user_request
        )

        # Get the created instruction details
        instructions = ryumem.list_agent_instructions(
            agent_type=request.agent_type,
            instruction_type=request.instruction_type,
            limit=1
        )

        if not instructions:
            raise HTTPException(status_code=500, detail="Failed to retrieve created instruction")

        created = instructions[0]

        return AgentInstructionResponse(
            instruction_id=created["instruction_id"],
            instruction_text=created["instruction_text"],
            name=created["name"],
            agent_type=created["agent_type"],
            instruction_type=created["instruction_type"],
            version=created["version"],
            description=created["description"],
            original_user_request=created.get("original_user_request", ""),
            converted_instruction=created.get("converted_instruction", created["instruction_text"]),
            created_at=created["created_at"]
        )

    except Exception as e:
        logger.error(f"Error creating agent instruction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating agent instruction: {str(e)}")


@app.get("/agent-instructions", response_model=List[AgentInstructionResponse], tags=["Agent Instructions"])
async def list_agent_instructions(
    agent_type: Optional[str] = None,
    instruction_type: Optional[str] = None,
    limit: int = 50,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    List all agent instructions with optional filters.

    Returns instructions ordered by creation date (newest first).
    """
    try:
        instructions = ryumem.list_agent_instructions(
            agent_type=agent_type,
            instruction_type=instruction_type,
            limit=limit
        )

        return [
            AgentInstructionResponse(
                instruction_id=instr["instruction_id"],
                instruction_text=instr["instruction_text"],
                name=instr["name"],
                agent_type=instr["agent_type"],
                instruction_type=instr["instruction_type"],
                version=instr["version"],
                description=instr["description"],
                original_user_request=instr.get("original_user_request", ""),
                converted_instruction=instr.get("converted_instruction", instr["instruction_text"]),
                created_at=instr["created_at"]
            )
            for instr in instructions
        ]

    except Exception as e:
        logger.error(f"Error listing agent instructions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing agent instructions: {str(e)}")


# ============================================================================
# Tool Analytics Endpoints
# ============================================================================

class ToolMetricsResponse(BaseModel):
    """Response model for detailed tool metrics"""
    tool_name: str
    usage_count: int
    success_rate: float
    avg_duration_ms: float
    recent_errors: List[str]


class ToolPreferenceResponse(BaseModel):
    """Response model for user tool preferences"""
    tool_name: str
    usage_count: int
    last_used: str


@app.get("/tools", tags=["Tool Analytics"])
async def get_all_tools(ryumem: Ryumem = Depends(get_ryumem)):
    """
    Get all registered tools.

    Returns list of all tools with their descriptions.
    """
    try:
        tools = ryumem.get_all_tools()
        return tools

    except Exception as e:
        logger.error(f"Error getting tools: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting tools: {str(e)}")


@app.get("/tools/{tool_name}/metrics", response_model=ToolMetricsResponse, tags=["Tool Analytics"])
async def get_tool_metrics(
    tool_name: str,
    user_id: Optional[str] = None,
    min_executions: int = 1,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get detailed metrics for a specific tool.

    Includes success rate, usage count, average duration, and recent errors.
    """
    try:
        metrics = ryumem.get_tool_success_rate(
            tool_name=tool_name,
            user_id=user_id,
            min_executions=min_executions
        )

        if not metrics:
            raise HTTPException(status_code=404, detail=f"No metrics found for tool: {tool_name}")

        return ToolMetricsResponse(
            tool_name=metrics["tool_name"],
            usage_count=metrics["usage_count"],
            success_rate=metrics["success_rate"],
            avg_duration_ms=metrics["avg_duration_ms"],
            recent_errors=metrics.get("recent_errors", [])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting tool metrics: {str(e)}")


@app.get("/users/{user_id}/tool-preferences", response_model=List[ToolPreferenceResponse], tags=["Tool Analytics"])
async def get_user_tool_preferences(
    user_id: str,
    limit: int = 10,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get user's most frequently used tools.

    Returns tools ordered by usage frequency.
    """
    try:
        preferences = ryumem.get_user_tool_preferences(
            user_id=user_id,
            limit=limit
        )

        return [
            ToolPreferenceResponse(
                tool_name=pref["tool_name"],
                usage_count=pref["usage_count"],
                last_used=pref.get("last_used", "")
            )
            for pref in preferences
        ]

    except Exception as e:
        logger.error(f"Error getting user tool preferences: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting user tool preferences: {str(e)}")


class QueryEpisodeResponse(BaseModel):
    """Response model for query episodes with metadata"""
    episode_id: str
    query: str
    user_id: str
    session_id: Optional[str]
    created_at: str
    runs: List[QueryRun]


@app.get("/augmented-queries", response_model=List[QueryEpisodeResponse], tags=["Query Augmentation"])
async def get_augmented_queries(
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    only_augmented: bool = False,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get all user queries with augmentation metadata.

    Args:
        user_id: Filter by user ID (optional)
        limit: Maximum number of queries to return
        offset: Number of queries to skip
        only_augmented: If True, only return queries that were augmented

    Returns:
        List of queries with augmentation details
    """
    try:
        # Get episodes from database with message source type (user queries)
        result = ryumem.db.get_episodes(
            user_id=user_id,
            limit=limit,
            offset=offset,
            sort_order="desc"
        )

        episodes = result.get("episodes", [])

        # Filter for message type episodes (user queries)
        query_episodes = []
        for episode in episodes:
            # Check if episode is a user query (source == "message")
            if episode.get("source") != "message":
                continue

            # Parse metadata (comes as JSON string from database)
            metadata_str = episode.get("metadata", "{}")
            try:
                metadata_dict = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata for episode {episode.get('uuid')}: {metadata_str}")
                continue

            # Parse into EpisodeMetadata model
            try:
                episode_metadata = EpisodeMetadata(**metadata_dict)
            except Exception as e:
                logger.warning(f"Failed to parse EpisodeMetadata for episode {episode.get('uuid')}: {e}")
                continue

            # Handle session_id (can be nan from database)
            session_id = episode.get("session_id")
            if session_id is not None and (isinstance(session_id, float) or str(session_id).lower() == 'nan'):
                session_id = None

            # Flatten all runs from all sessions
            runs = []
            for session_runs in episode_metadata.sessions.values():
                runs.extend(session_runs)

            # If only_augmented is True, filter runs that have augmented queries
            if only_augmented:
                runs = [run for run in runs if run.augmented_query and run.augmented_query != run.query]
                if not runs:
                    continue

            query_episodes.append(
                QueryEpisodeResponse(
                    episode_id=episode["uuid"],
                    query=episode["content"],
                    user_id=episode["user_id"],
                    session_id=session_id,
                    created_at=episode["created_at"].isoformat() if hasattr(episode["created_at"], "isoformat") else str(episode["created_at"]),
                    runs=runs
                )
            )

        return query_episodes

    except Exception as e:
        logger.error(f"Error getting augmented queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting augmented queries: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

