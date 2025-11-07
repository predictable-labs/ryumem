"""
FastAPI Server for Ryumem - Bi-temporal Knowledge Graph Memory System

This server provides RESTful API endpoints for:
- Adding episodes (memories)
- Searching/querying the knowledge graph
- Getting entity context
- Managing communities and memory pruning

Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ryumem import Ryumem

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global Ryumem instance
ryumem_instance: Optional[Ryumem] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup Ryumem on startup/shutdown"""
    global ryumem_instance
    
    logger.info("Starting Ryumem server...")
    
    # Initialize Ryumem
    db_path = os.getenv("RYUMEM_DB_PATH", "./data/ollama_memory.db")
    
    # Ensure data directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    ryumem_instance = Ryumem(
        db_path=db_path,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        llm_provider=os.getenv("RYUMEM_LLM_PROVIDER", "openai"),
        llm_model=os.getenv("RYUMEM_LLM_MODEL", "gpt-4o-mini"),
        ollama_base_url=os.getenv("RYUMEM_OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    
    logger.info(f"Ryumem initialized: {ryumem_instance}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Ryumem server...")
    if ryumem_instance:
        ryumem_instance.close()
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
    group_id: str = Field(..., description="Group ID for multi-tenancy")
    user_id: Optional[str] = Field(None, description="Optional user ID")
    agent_id: Optional[str] = Field(None, description="Optional agent ID")
    session_id: Optional[str] = Field(None, description="Optional session ID")
    source: str = Field("text", description="Episode source type: text, message, or json")
    metadata: Optional[Dict] = Field(None, description="Optional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Alice works at Google as a Software Engineer in Mountain View.",
                "group_id": "user_123",
                "user_id": "user_123",
                "source": "text"
            }
        }


class AddEpisodeResponse(BaseModel):
    """Response model for adding an episode"""
    episode_id: str = Field(..., description="UUID of the created episode")
    message: str = Field(..., description="Success message")
    timestamp: str = Field(..., description="Timestamp of creation")


class SearchRequest(BaseModel):
    """Request model for searching"""
    query: str = Field(..., description="Search query text")
    group_id: str = Field(..., description="Group ID to search within")
    user_id: Optional[str] = Field(None, description="Optional user ID filter")
    limit: int = Field(10, description="Maximum number of results", ge=1, le=100)
    strategy: str = Field("hybrid", description="Search strategy: semantic, bm25, traversal, or hybrid")
    min_rrf_score: Optional[float] = Field(None, description="Minimum RRF score for hybrid search")
    min_bm25_score: Optional[float] = Field(None, description="Minimum BM25 score")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Where does Alice work?",
                "group_id": "user_123",
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
    group_id: str = Field(..., description="Group ID to detect communities for")
    resolution: float = Field(1.0, description="Resolution parameter for Louvain algorithm", ge=0.1, le=5.0)
    min_community_size: int = Field(2, description="Minimum number of entities per community", ge=1)


class UpdateCommunitiesResponse(BaseModel):
    """Response model for updating communities"""
    num_communities: int = Field(..., description="Number of communities created")
    message: str = Field(..., description="Success message")


class PruneMemoriesRequest(BaseModel):
    """Request model for pruning memories"""
    group_id: str = Field(..., description="Group ID to prune")
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


# ===== API Endpoints =====

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        ryumem_initialized=ryumem_instance is not None,
        timestamp=datetime.now().isoformat()
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        ryumem_initialized=ryumem_instance is not None,
        timestamp=datetime.now().isoformat()
    )


@app.post("/episodes", response_model=AddEpisodeResponse)
async def add_episode(request: AddEpisodeRequest):
    """
    Add a new episode to the memory system.
    
    This will:
    1. Create an episode node
    2. Extract entities and relationships
    3. Update the knowledge graph
    4. Detect and handle contradictions
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        episode_id = ryumem_instance.add_episode(
            content=request.content,
            group_id=request.group_id,
            user_id=request.user_id,
            agent_id=request.agent_id,
            session_id=request.session_id,
            source=request.source,
            metadata=request.metadata,
        )
        
        return AddEpisodeResponse(
            episode_id=episode_id,
            message="Episode added successfully",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error adding episode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error adding episode: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search the knowledge graph.
    
    Supports multiple strategies:
    - semantic: Embedding-based similarity search
    - bm25: Keyword-based search
    - traversal: Graph-based navigation
    - hybrid: Combines all strategies (recommended)
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        results = ryumem_instance.search(
            query=request.query,
            group_id=request.group_id,
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
    group_id: str,
    user_id: Optional[str] = None,
    max_depth: int = 2
):
    """
    Get comprehensive context for an entity by name.
    
    Returns:
    - Entity details
    - All relationships
    - Related entities
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        context = ryumem_instance.get_entity_context(
            entity_name=entity_name,
            group_id=group_id,
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
async def get_stats(group_id: Optional[str] = None):
    """
    Get system statistics.
    
    Returns counts of episodes, entities, relationships, and communities.
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        # Query database for stats
        group_filter = f"WHERE e.group_id = '{group_id}'" if group_id else ""
        
        # Count episodes
        episode_query = f"""
        MATCH (ep:Episode)
        {group_filter.replace('e.', 'ep.')}
        RETURN COUNT(ep) AS count
        """
        episode_result = ryumem_instance.db.execute(episode_query, {})
        total_episodes = episode_result[0]["count"] if episode_result else 0
        
        # Count entities
        entity_query = f"""
        MATCH (e:Entity)
        {group_filter}
        RETURN COUNT(e) AS count
        """
        entity_result = ryumem_instance.db.execute(entity_query, {})
        total_entities = entity_result[0]["count"] if entity_result else 0
        
        # Count relationships
        rel_query = f"""
        MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity)
        {group_filter.replace('e.', 's.')}
        RETURN COUNT(r) AS count
        """
        rel_result = ryumem_instance.db.execute(rel_query, {})
        total_relationships = rel_result[0]["count"] if rel_result else 0
        
        # Count communities
        comm_query = f"""
        MATCH (c:Community)
        {group_filter.replace('e.', 'c.')}
        RETURN COUNT(c) AS count
        """
        comm_result = ryumem_instance.db.execute(comm_query, {})
        total_communities = comm_result[0]["count"] if comm_result else 0
        
        return StatsResponse(
            total_episodes=total_episodes,
            total_entities=total_entities,
            total_relationships=total_relationships,
            total_communities=total_communities,
            db_path=ryumem_instance.config.db_path
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.post("/communities/update", response_model=UpdateCommunitiesResponse)
async def update_communities(request: UpdateCommunitiesRequest):
    """
    Detect and update communities using Louvain algorithm.
    
    Communities cluster related entities together for:
    - More efficient retrieval
    - Higher-level reasoning
    - Better organization
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        num_communities = ryumem_instance.update_communities(
            group_id=request.group_id,
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
async def prune_memories(request: PruneMemoriesRequest):
    """
    Prune and compact memories to keep the graph efficient.
    
    This performs:
    - Delete facts that were invalidated/expired long ago
    - Remove entities with very few mentions (likely noise)
    - Merge near-duplicate relationship facts
    """
    if not ryumem_instance:
        raise HTTPException(status_code=503, detail="Ryumem not initialized")
    
    try:
        stats = ryumem_instance.prune_memories(
            group_id=request.group_id,
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


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

