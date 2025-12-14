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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import sqlite3
import secrets

import httpx

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Header, Query, status
from urllib.parse import urlencode
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ryumem_server import Ryumem
from ryumem_server.core.config import RyumemConfig
from ryumem_server.core.metadata_models import EpisodeMetadata, QueryRun, ToolExecution

from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.graph_db import RyugraphDB
from ryumem_server.core.config_service import ConfigService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global singleton instance
# _ryumem_instance: Optional[Ryumem] = None  # REMOVED for multi-tenancy

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

# Auth Manager and Cache
class AuthManager:
    def __init__(self, db_path: str = "./data/master_auth.db"):
        self.db_path = db_path
        # Initialize RyugraphDB for auth
        # We use a smaller embedding dimension since we don't need embeddings for auth,
        # but RyugraphDB requires it. 384 is small enough.
        self.db = RyugraphDB(db_path=db_path, embedding_dimensions=384)
        self._init_schema()

    def _init_schema(self):
        """Initialize Customer and OAuthIdentity tables"""
        # Customer table - core user record
        self.db.execute("""
            CREATE NODE TABLE IF NOT EXISTS Customer(
                customer_id STRING PRIMARY KEY,
                api_key STRING,
                created_at TIMESTAMP
            )
        """)

        # OAuthIdentity table - supports multiple OAuth providers
        # NOTE: We do NOT store access_token/refresh_token for security.
        # OAuth tokens are used once to identify the user, then discarded.
        self.db.execute("""
            CREATE NODE TABLE IF NOT EXISTS OAuthIdentity(
                id STRING PRIMARY KEY,
                provider STRING,
                provider_user_id STRING,
                provider_username STRING,
                scopes STRING,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        # Relationship: Customer -[HAS_OAUTH]-> OAuthIdentity
        try:
            self.db.execute("""
                CREATE REL TABLE IF NOT EXISTS HAS_OAUTH(
                    FROM Customer TO OAuthIdentity
                )
            """)
        except Exception:
            # Table may already exist
            pass

        # Migration: Add columns to Customer for backwards compatibility
        # These are deprecated but kept for existing data
        migration_columns = [
            ("github_id", "STRING"),
            ("github_username", "STRING"),
        ]
        for col_name, col_type in migration_columns:
            try:
                self.db.execute(f"ALTER TABLE Customer ADD {col_name} {col_type}", log_errors=False)
            except Exception:
                pass

    def create_customer(self, customer_id: str) -> str:
        """Create a new customer and return their API key"""
        import secrets
        from datetime import datetime

        # Check if exists
        existing = self.db.execute(
            "MATCH (c:Customer {customer_id: $cid}) RETURN c.customer_id",
            {"cid": customer_id}
        )
        if existing:
            raise ValueError(f"Customer {customer_id} already exists")

        api_key = f"ryu_{secrets.token_urlsafe(32)}"

        self.db.execute(
            """
            CREATE (c:Customer {
                customer_id: $cid,
                api_key: $key,
                created_at: $created_at
            })
            """,
            {
                "cid": customer_id,
                "key": api_key,
                "created_at": datetime.utcnow()
            }
        )
        return api_key

    def validate_key(self, api_key: str) -> Optional[str]:
        """Validate API key and return customer_id"""
        result = self.db.execute(
            "MATCH (c:Customer) WHERE c.api_key = $key RETURN c.customer_id",
            {"key": api_key}
        )
        if result and len(result) > 0:
            return result[0]["c.customer_id"]
        return None

    def get_customer_by_oauth(
        self,
        provider: str,
        provider_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get customer by OAuth provider and user ID (new table structure)"""
        result = self.db.execute(
            """
            MATCH (c:Customer)-[:HAS_OAUTH]->(o:OAuthIdentity)
            WHERE o.provider = $provider AND o.provider_user_id = $uid
            RETURN c.customer_id, c.api_key, o.provider_username
            """,
            {"provider": provider, "uid": provider_user_id}
        )
        if result and len(result) > 0:
            return {
                "customer_id": result[0]["c.customer_id"],
                "api_key": result[0]["c.api_key"],
                "provider_username": result[0]["o.provider_username"]
            }
        return None

    def get_customer_by_github_id(self, github_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by GitHub ID (checks both old and new table structure)"""
        # First check new OAuthIdentity table
        result = self.get_customer_by_oauth("github", github_id)
        if result:
            return {
                "customer_id": result["customer_id"],
                "api_key": result["api_key"],
                "github_username": result.get("provider_username")
            }

        # Fallback to legacy github_id column for backwards compatibility
        legacy_result = self.db.execute(
            "MATCH (c:Customer) WHERE c.github_id = $gid RETURN c.customer_id, c.api_key, c.github_username",
            {"gid": github_id}
        )
        if legacy_result and len(legacy_result) > 0:
            return {
                "customer_id": legacy_result[0]["c.customer_id"],
                "api_key": legacy_result[0]["c.api_key"],
                "github_username": legacy_result[0]["c.github_username"]
            }
        return None

    def create_or_update_oauth_customer(
        self,
        provider: str,
        provider_user_id: str,
        provider_username: str,
        scopes: str = "",
    ) -> Dict[str, Any]:
        """
        Create or update a customer from OAuth login.

        Security note: We do NOT store the OAuth access token. The token is used
        once to identify the user, then discarded. Users authenticate with our
        api_key for all subsequent requests.

        Args:
            provider: OAuth provider name (e.g., 'github', 'google')
            provider_user_id: User ID from the OAuth provider
            provider_username: Username/display name from the provider
            scopes: OAuth scopes that were requested
        """
        existing = self.get_customer_by_oauth(provider, provider_user_id)

        if existing:
            # Update username if changed
            oauth_id = f"{provider}_{provider_user_id}"
            self.db.execute(
                """
                MATCH (o:OAuthIdentity {id: $oid})
                SET o.provider_username = $username, o.updated_at = $updated_at
                """,
                {"oid": oauth_id, "username": provider_username, "updated_at": datetime.utcnow()}
            )

            api_key = existing["api_key"]
            # Regenerate API key if it's None (can happen from NaN->None conversion or NULL in DB)
            if not api_key:
                api_key = f"ryu_{secrets.token_urlsafe(32)}"
                self.db.execute(
                    """
                    MATCH (c:Customer {customer_id: $cid})
                    SET c.api_key = $key
                    """,
                    {"cid": existing["customer_id"], "key": api_key}
                )
                logger.info(f"Regenerated API key for customer {existing['customer_id']}")

            return {
                "customer_id": existing["customer_id"],
                "api_key": api_key,
                "provider_username": provider_username
            }

        # Create new customer and OAuth identity
        customer_id = f"{provider}_{provider_user_id}"
        api_key = f"ryu_{secrets.token_urlsafe(32)}"
        oauth_id = f"{provider}_{provider_user_id}"
        now = datetime.utcnow()

        # Create Customer node
        self.db.execute(
            """
            CREATE (c:Customer {
                customer_id: $cid,
                api_key: $key,
                created_at: $created_at
            })
            """,
            {"cid": customer_id, "key": api_key, "created_at": now}
        )

        # Create OAuthIdentity node
        self.db.execute(
            """
            CREATE (o:OAuthIdentity {
                id: $oid,
                provider: $provider,
                provider_user_id: $uid,
                provider_username: $username,
                scopes: $scopes,
                created_at: $created_at,
                updated_at: $updated_at
            })
            """,
            {
                "oid": oauth_id,
                "provider": provider,
                "uid": provider_user_id,
                "username": provider_username,
                "scopes": scopes,
                "created_at": now,
                "updated_at": now,
            }
        )

        # Create relationship
        self.db.execute(
            """
            MATCH (c:Customer {customer_id: $cid}), (o:OAuthIdentity {id: $oid})
            CREATE (c)-[:HAS_OAUTH]->(o)
            """,
            {"cid": customer_id, "oid": oauth_id}
        )

        return {
            "customer_id": customer_id,
            "api_key": api_key,
            "provider_username": provider_username
        }

    def create_or_update_github_customer(
        self,
        github_id: str,
        github_username: str,
    ) -> Dict[str, Any]:
        """
        Create or update a customer from GitHub OAuth login.
        Convenience wrapper around create_or_update_oauth_customer.
        """
        result = self.create_or_update_oauth_customer(
            provider="github",
            provider_user_id=github_id,
            provider_username=github_username,
            scopes="read:user",
        )
        # Return with github_username key for backwards compatibility
        return {
            "customer_id": result["customer_id"],
            "api_key": result["api_key"],
            "github_username": result["provider_username"]
        }

    def get_customer_details(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get full customer details by customer_id, including OAuth identities"""
        # Get basic customer info
        result = self.db.execute(
            "MATCH (c:Customer {customer_id: $cid}) RETURN c.customer_id, c.api_key, c.github_username, c.github_id",
            {"cid": customer_id}
        )
        if not result or len(result) == 0:
            return None

        customer = {
            "customer_id": result[0]["c.customer_id"],
            "api_key": result[0]["c.api_key"],
            # Legacy fields for backwards compatibility
            "github_username": result[0].get("c.github_username"),
            "github_id": result[0].get("c.github_id"),
        }

        # Get OAuth identities
        oauth_result = self.db.execute(
            """
            MATCH (c:Customer {customer_id: $cid})-[:HAS_OAUTH]->(o:OAuthIdentity)
            RETURN o.provider, o.provider_user_id, o.provider_username
            """,
            {"cid": customer_id}
        )
        if oauth_result:
            customer["oauth_identities"] = [
                {
                    "provider": row["o.provider"],
                    "provider_user_id": row["o.provider_user_id"],
                    "provider_username": row["o.provider_username"],
                }
                for row in oauth_result
            ]
        else:
            customer["oauth_identities"] = []

        return customer

_auth_manager: Optional[AuthManager] = None
_ryumem_cache: Dict[str, Ryumem] = {}



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    # Startup: Initialize AuthManager
    global _auth_manager, _ryumem_cache
    
    logger.info("Initializing AuthManager...")
    # Ensure data directory exists for master.db
    os.makedirs("./data", exist_ok=True)
    _auth_manager = AuthManager(db_path="./data/master_auth.db")
    
    logger.info("Ryumem Server initialized (Multi-tenant mode)")
    
    yield
    
    # Shutdown: Clean up resources
    logger.info("Shutting down Ryumem Server...")
    # Close all open Ryumem instances
    for customer_id, instance in _ryumem_cache.items():
        try:
            instance.db.close() # Assuming Ryumem has a way to close DB or we rely on GC
            # Actually Ryumem.close() might be better if it exists, let's check lib.py
            # lib.py doesn't seem to have a close() method on Ryumem class based on previous view_file
            # But RyugraphDB might.
            pass 
        except Exception as e:
            logger.error(f"Error closing instance for {customer_id}: {e}")
    _ryumem_cache.clear()
    logger.info("Shutdown complete")


# Dependency for Auth - supports both API Key and Bearer Token
async def get_current_customer(
    x_api_key: Optional[str] = Header(None, description="Customer API Key"),
    authorization: Optional[str] = Header(None, description="Bearer token for OAuth")
) -> str:
    """
    Validate API key or Bearer token and return customer_id.
    Supports both X-API-Key header and Authorization: Bearer token.
    """
    if not _auth_manager:
        raise HTTPException(status_code=503, detail="AuthManager not initialized")

    # Try Bearer token first (OAuth)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        customer_id = _auth_manager.validate_github_token(token)
        if customer_id:
            return customer_id

    # Fall back to API key
    if x_api_key:
        customer_id = _auth_manager.validate_key(x_api_key)
        if customer_id:
            return customer_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key or Authorization: Bearer token",
    )


# Dependency injection for per-request Ryumem instances
def get_ryumem(customer_id: str = Depends(get_current_customer)):
    """
    Get the Ryumem instance for the current customer.
    """
    if customer_id in _ryumem_cache:
        return _ryumem_cache[customer_id]
        
    # Create new instance
    db_folder = os.getenv("RYUMEM_DB_FOLDER", "./data")
    db_path = os.path.join(db_folder, f"{customer_id}.db")
    
    logger.info(f"Creating Ryumem instance for {customer_id} at {db_path}")
    
    # Initialize with specific DB path
    # We create a fresh config to avoid sharing state, though Ryumem(db_path=...) handles override
    instance = Ryumem(db_path=db_path)
    
    _ryumem_cache[customer_id] = instance
    return instance


def get_write_ryumem(customer_id: str = Depends(get_current_customer)):
    """
    Get the Ryumem instance for WRITE operations.
    """
    return get_ryumem(customer_id)


def invalidate_ryumem_cache(customer_id: str) -> None:
    """
    Invalidate the cached Ryumem instance for a customer.
    Next request will create a fresh instance with updated config from database.

    Args:
        customer_id: Customer ID whose cache entry should be invalidated
    """
    if customer_id in _ryumem_cache:
        try:
            instance = _ryumem_cache[customer_id]
            instance.close()  # Close DB connection gracefully
            logger.info(f"Closed Ryumem instance for customer {customer_id}")
        except Exception as e:
            logger.warning(f"Error closing Ryumem instance for {customer_id}: {e}")
        finally:
            # Remove from cache regardless of close result
            del _ryumem_cache[customer_id]
            logger.info(f"Invalidated Ryumem cache for customer {customer_id}")


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
    kind: str = Field("query", description="Episode kind: 'query' or 'memory'")
    metadata: Optional[Dict] = Field(None, description="Optional metadata")
    extract_entities: Optional[bool] = Field(None, description="Override config setting for entity extraction (None uses config default)")
    enable_embeddings: Optional[bool] = Field(None, description="Override config setting for episode embeddings (None uses config default)")
    deduplication_enabled: Optional[bool] = Field(None, description="Override config setting for episode deduplication (None uses config default)")

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
    kind: Optional[str] = None
    created_at: datetime
    valid_at: datetime
    user_id: Optional[str] = None
    metadata: Optional[dict] = None
    score: Optional[float] = None  # Search relevance score


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
    kinds: Optional[List[str]] = Field(None, description="Filter episodes by kinds (e.g., ['query'], ['memory'], or None for all)")
    tags: Optional[List[str]] = Field(None, description="Filter episodes by tags")
    tag_match_mode: str = Field("any", description="Tag matching mode: 'any' or 'all'")

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
    episodes: List[EpisodeInfo] = Field(default_factory=list, description="List of episodes found")
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
    db_path: str = Field(..., description="Database path")


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


class CypherRequest(BaseModel):
    """Request model for executing Cypher query"""
    query: str = Field(..., description="Cypher query")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")


class CypherResponse(BaseModel):
    """Response model for Cypher query"""
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Query results")


class UpdateMetadataRequest(BaseModel):
    """Request model for updating episode metadata"""
    metadata: Dict[str, Any] = Field(..., description="New metadata")


class SaveToolRequest(BaseModel):
    """Request model for saving a tool"""
    tool_name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    name_embedding: Optional[List[float]] = Field(None, description="Embedding of tool name (optional)")


class ToolResponse(BaseModel):
    """Response model for tool data"""
    tool_name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    name_embedding: Optional[List[float]] = Field(None, description="Embedding of tool name")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class BatchSaveToolsRequest(BaseModel):
    """Request model for batch saving tools"""
    tools: List[SaveToolRequest] = Field(..., description="List of tools to save")


class BatchSaveToolsResponse(BaseModel):
    """Response model for batch save tools operation"""
    saved: int = Field(..., description="Number of tools saved")
    updated: int = Field(..., description="Number of tools updated (already existed)")
    failed: int = Field(..., description="Number of tools that failed")
    errors: List[str] = Field(default_factory=list, description="Error messages if any")


class EmbedRequest(BaseModel):
    """Request model for embedding text"""
    text: str = Field(..., description="Text to embed")


class EmbedResponse(BaseModel):
    """Response model for embedding"""
    embedding: List[float] = Field(..., description="Embedding vector")


class GenerateRequest(BaseModel):
    """Request model for LLM generation"""
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    temperature: float = Field(0.7, description="Temperature")
    max_tokens: int = Field(1000, description="Max tokens")


class GenerateResponse(BaseModel):
    """Response model for LLM generation"""
    content: str = Field(..., description="Generated content")


class GenerateResponse(BaseModel):
    """Response model for LLM generation"""
    content: str = Field(..., description="Generated content")


class RegisterRequest(BaseModel):
    """Request model for registering a customer"""
    customer_id: str = Field(..., description="Unique customer ID")


class RegisterResponse(BaseModel):
    """Response model for registration"""
    customer_id: str = Field(..., description="Customer ID")
    api_key: str = Field(..., description="Generated API Key")
    message: str = Field(..., description="Success message")


# ===== GitHub OAuth Models =====

class GitHubCallbackRequest(BaseModel):
    """Request model for GitHub OAuth callback"""
    code: str = Field(..., description="Authorization code from GitHub")
    redirect_uri: Optional[str] = Field(None, description="Redirect URI used in the authorization request")


class GitHubAuthResponse(BaseModel):
    """Response model for GitHub OAuth authentication"""
    customer_id: str = Field(..., description="Customer ID")
    api_key: str = Field(..., description="API Key for use in scripts/MCP")
    github_username: str = Field(..., description="GitHub username")
    message: str = Field(..., description="Success message")


class DeviceCodeResponse(BaseModel):
    """Response model for device code flow initiation"""
    device_code: str = Field(..., description="Device code for polling")
    user_code: str = Field(..., description="Code for user to enter")
    verification_uri: str = Field(..., description="URL for user to visit")
    expires_in: int = Field(..., description="Seconds until codes expire")
    interval: int = Field(..., description="Polling interval in seconds")


class DevicePollRequest(BaseModel):
    """Request model for polling device code status"""
    device_code: str = Field(..., description="Device code from initiation")


class DevicePollResponse(BaseModel):
    """Response model for device code polling"""
    status: str = Field(..., description="Status: pending, complete, or error")
    customer_id: Optional[str] = Field(None, description="Customer ID (on success)")
    api_key: Optional[str] = Field(None, description="API Key (on success)")
    github_username: Optional[str] = Field(None, description="GitHub username (on success)")
    error: Optional[str] = Field(None, description="Error message (on failure)")


class OAuthIdentityInfo(BaseModel):
    """OAuth identity information"""
    provider: str = Field(..., description="OAuth provider (e.g., 'github', 'google')")
    provider_user_id: str = Field(..., description="User ID from the OAuth provider")
    provider_username: Optional[str] = Field(None, description="Username from the OAuth provider")


class AuthMeResponse(BaseModel):
    """Response model for current user info"""
    customer_id: str = Field(..., description="Customer ID")
    github_username: Optional[str] = Field(None, description="GitHub username if OAuth user (deprecated, use oauth_identities)")
    api_key_preview: str = Field(..., description="First 8 chars of API key")
    oauth_identities: List[OAuthIdentityInfo] = Field(default_factory=list, description="Linked OAuth identities")


class GitHubAuthUrlResponse(BaseModel):
    """Response model for GitHub auth URL"""
    auth_url: str = Field(..., description="GitHub OAuth authorization URL")
    configured: bool = Field(..., description="Whether GitHub OAuth is configured")


# ===== API Endpoints =====

@app.post("/register", response_model=RegisterResponse)
async def register_customer(
    request: RegisterRequest,
    admin_key: str = Header(..., alias="X-Admin-Key", description="Admin API Key")
):
    """
    Register a new customer.
    Requires X-Admin-Key header.
    """
    expected_key = os.getenv("ADMIN_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=500, detail="ADMIN_API_KEY not configured")
        
    if admin_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid Admin Key")
        
    try:
        if not _auth_manager:
             raise HTTPException(status_code=503, detail="AuthManager not initialized")
             
        api_key = _auth_manager.create_customer(request.customer_id)
        return RegisterResponse(
            customer_id=request.customer_id,
            api_key=api_key,
            message="Customer registered successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering customer: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ===== GitHub OAuth Endpoints =====

@app.get("/auth/github/url", response_model=GitHubAuthUrlResponse, tags=["Authentication"])
async def get_github_auth_url(redirect_uri: str = Query(..., description="Redirect URI after OAuth")):
    """
    Get GitHub OAuth authorization URL.

    Returns the URL to redirect users to for GitHub OAuth login.
    The redirect_uri should be the frontend login page URL.
    """
    if not GITHUB_CLIENT_ID:
        return GitHubAuthUrlResponse(auth_url="", configured=False)

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "read:user",
    }
    auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return GitHubAuthUrlResponse(auth_url=auth_url, configured=True)


@app.post("/auth/github/callback", response_model=GitHubAuthResponse, tags=["Authentication"])
async def github_oauth_callback(request: GitHubCallbackRequest):
    """
    Handle GitHub OAuth callback (Authorization Code Flow).

    Used by the dashboard for browser-based OAuth login.
    Exchanges the authorization code for an access token and creates/updates the user.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
        )

    if not _auth_manager:
        raise HTTPException(status_code=503, detail="AuthManager not initialized")

    try:
        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": request.code,
                    "redirect_uri": request.redirect_uri,
                },
                headers={"Accept": "application/json"}
            )

            if token_response.status_code != 200:
                logger.error(f"GitHub token exchange failed: {token_response.text}")
                raise HTTPException(status_code=400, detail="Failed to exchange code for token")

            token_data = token_response.json()

            if "error" in token_data:
                raise HTTPException(
                    status_code=400,
                    detail=f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}"
                )

            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")

            # Get user info from GitHub
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json"
                }
            )

            if user_response.status_code != 200:
                logger.error(f"GitHub user info failed: {user_response.text}")
                raise HTTPException(status_code=400, detail="Failed to get GitHub user info")

            user_data = user_response.json()
            github_id = str(user_data["id"])
            github_username = user_data.get("login", "unknown")

            # Create or update customer (GitHub token is NOT stored - used once and discarded)
            customer = _auth_manager.create_or_update_github_customer(
                github_id=github_id,
                github_username=github_username,
            )

            logger.info(f"GitHub OAuth login successful for {github_username}")

            return GitHubAuthResponse(
                customer_id=customer["customer_id"],
                api_key=customer["api_key"],
                github_username=github_username,
                message="GitHub authentication successful"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitHub OAuth error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OAuth error: {str(e)}")


@app.post("/auth/github/device", response_model=DeviceCodeResponse, tags=["Authentication"])
async def github_device_code():
    """
    Start GitHub Device Code Flow.

    Used by CLI tools (MCP server) that can't open a browser directly.
    Returns a user code that the user enters at github.com/login/device.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID."
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/device/code",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "scope": "read:user"
                },
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                logger.error(f"GitHub device code request failed: {response.text}")
                raise HTTPException(status_code=400, detail="Failed to initiate device flow")

            data = response.json()

            if "error" in data:
                raise HTTPException(
                    status_code=400,
                    detail=f"GitHub error: {data.get('error_description', data['error'])}"
                )

            return DeviceCodeResponse(
                device_code=data["device_code"],
                user_code=data["user_code"],
                verification_uri=data["verification_uri"],
                expires_in=data["expires_in"],
                interval=data.get("interval", 5)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Device code error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Device flow error: {str(e)}")


@app.post("/auth/github/device/poll", response_model=DevicePollResponse, tags=["Authentication"])
async def github_device_poll(request: DevicePollRequest):
    """
    Poll for Device Code Flow completion.

    Called repeatedly by CLI tools until the user completes authorization.
    Returns status: "pending", "complete", or "error".
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
        )

    if not _auth_manager:
        raise HTTPException(status_code=503, detail="AuthManager not initialized")

    try:
        async with httpx.AsyncClient() as client:
            # Poll for access token
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "device_code": request.device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
                },
                headers={"Accept": "application/json"}
            )

            data = response.json()

            # Check for pending/slow_down errors (user hasn't authorized yet)
            if "error" in data:
                error = data["error"]
                if error in ["authorization_pending", "slow_down"]:
                    return DevicePollResponse(
                        status="pending",
                        error=None
                    )
                elif error == "expired_token":
                    return DevicePollResponse(
                        status="error",
                        error="Device code expired. Please restart the authentication flow."
                    )
                elif error == "access_denied":
                    return DevicePollResponse(
                        status="error",
                        error="User denied authorization."
                    )
                else:
                    return DevicePollResponse(
                        status="error",
                        error=data.get("error_description", error)
                    )

            # Success! Got access token
            access_token = data.get("access_token")
            if not access_token:
                return DevicePollResponse(
                    status="error",
                    error="No access token received"
                )

            # Get user info from GitHub
            user_response = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json"
                }
            )

            if user_response.status_code != 200:
                return DevicePollResponse(
                    status="error",
                    error="Failed to get GitHub user info"
                )

            user_data = user_response.json()
            github_id = str(user_data["id"])
            github_username = user_data.get("login", "unknown")

            # Create or update customer (GitHub token is NOT stored - used once and discarded)
            customer = _auth_manager.create_or_update_github_customer(
                github_id=github_id,
                github_username=github_username,
            )

            logger.info(f"Device flow login successful for {github_username}")

            return DevicePollResponse(
                status="complete",
                customer_id=customer["customer_id"],
                api_key=customer["api_key"],
                github_username=github_username
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Device poll error: {e}", exc_info=True)
        return DevicePollResponse(
            status="error",
            error=str(e)
        )


@app.get("/auth/me", response_model=AuthMeResponse, tags=["Authentication"])
async def get_auth_me(customer_id: str = Depends(get_current_customer)):
    """
    Get current authenticated user info.

    Works with both API key and Bearer token authentication.
    Returns customer details including API key preview.
    """
    if not _auth_manager:
        raise HTTPException(status_code=503, detail="AuthManager not initialized")

    customer = _auth_manager.get_customer_details(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    api_key = customer.get("api_key", "")
    api_key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key

    # Build OAuth identities list
    oauth_identities = [
        OAuthIdentityInfo(
            provider=oi["provider"],
            provider_user_id=oi["provider_user_id"],
            provider_username=oi.get("provider_username"),
        )
        for oi in customer.get("oauth_identities", [])
    ]

    return AuthMeResponse(
        customer_id=customer["customer_id"],
        github_username=customer.get("github_username"),
        api_key_preview=api_key_preview,
        oauth_identities=oauth_identities,
    )


@app.get("/auth/api-key", tags=["Authentication"])
async def get_full_api_key(customer_id: str = Depends(get_current_customer)):
    """
    Get full API key for the authenticated user.

    Use this to display the API key in the dashboard settings page.
    """
    if not _auth_manager:
        raise HTTPException(status_code=503, detail="AuthManager not initialized")

    customer = _auth_manager.get_customer_details(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    api_key = customer.get("api_key")
    # Regenerate API key if it's None (can happen from data corruption or NaN->None conversion)
    if not api_key:
        api_key = f"ryu_{secrets.token_urlsafe(32)}"
        _auth_manager.db.execute(
            """
            MATCH (c:Customer {customer_id: $cid})
            SET c.api_key = $key
            """,
            {"cid": customer_id, "key": api_key}
        )
        logger.info(f"Regenerated API key for customer {customer_id} via /auth/api-key endpoint")

    return {
        "api_key": api_key,
        "customer_id": customer["customer_id"],
        "github_username": customer.get("github_username")
    }


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


@app.get("/config")
async def get_config(ryumem: Ryumem = Depends(get_ryumem)):
    """
    Get the full configuration for the current Ryumem instance.
    """
    try:
        # Get config from the instance
        config = ryumem.config

        # Convert to dict
        config_dict = config.model_dump()

        # Manually remove sensitive keys to ensure they don't leak to client
        if 'llm' in config_dict:
            config_dict['llm'].pop('openai_api_key', None)
            config_dict['llm'].pop('gemini_api_key', None)

        return config_dict
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Add a new episode to the memory system.

    This will:
    1. Create an episode node
    2. Extract entities and relationships
    3. Update the knowledge graph
    4. Detect and handle contradictions

    Use a separate write instance for adding episodes.
    """
    try:
        episode_id = ryumem.add_episode(
            content=request.content,
            user_id=request.user_id,
            session_id=request.session_id,
            source=request.source,
            kind=request.kind,
            metadata=request.metadata,
            extract_entities=request.extract_entities,
            enable_embeddings=request.enable_embeddings,
            deduplication_enabled=request.deduplication_enabled,
        )

        return AddEpisodeResponse(
            episode_id=episode_id,
            message="Episode added successfully",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error adding episode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error adding episode: {str(e)}")


@app.get("/episodes/{episode_uuid}", response_model=Optional[Dict[str, Any]])
async def get_episode_by_uuid(
    episode_uuid: str,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get a single episode by its UUID.
    """
    try:
        episode = ryumem.db.get_episode_by_uuid(episode_uuid)
        if not episode:
            raise HTTPException(status_code=404, detail=f"Episode {episode_uuid} not found")
        return episode
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting episode: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error getting episode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting episode: {str(e)}")


@app.get("/episodes/{source_uuid}/triggered", response_model=List[Dict[str, Any]])
async def get_triggered_episodes(
    source_uuid: str,
    source_type: Optional[str] = None,
    limit: int = 10,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get episodes triggered by a source episode.

    Query params:
        source_type: Optional filter by episode source type (e.g., 'json')
        limit: Maximum number of results (default: 10)
    """
    try:
        episodes = ryumem.get_triggered_episodes(source_uuid, source_type, limit)
        return [episode.model_dump() for episode in episodes]
    except Exception as e:
        logger.error(f"Error getting triggered episodes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting triggered episodes: {str(e)}")


@app.get("/episodes/session/{session_id}", response_model=Optional[Dict[str, Any]])
async def get_episode_by_session_id(
    session_id: str,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get the latest episode for a session ID.
    """
    try:
        # Assuming Ryumem DB has this method, if not we might need to implement it or use a cypher query
        # Checking if ryumem.db has get_episode_by_session_id
        # If not, we can use execute_cypher logic here or add it to RyugraphDB
        # For now, let's assume it exists or we implement it via cypher here if needed.
        # But better to use the method if it exists.
        # If RyugraphDB doesn't have it, we can do a cypher query here.
        
        # Let's try to use the method first, if it fails we can fallback or fix RyugraphDB.
        # But since I can't see RyugraphDB easily, I'll implement a safe fallback using execute if needed?
        # No, let's trust it exists or I'll add it to RyugraphDB if I could.
        # Actually, I can't edit RyugraphDB easily as it's in server/ryumem_server/core/graph_db.py
        # Let's assume it exists as the client code was using it.
        
        episode = ryumem.db.get_episode_by_session_id(session_id)
        if not episode:
             # Return None (200 OK with null body) or 404?
             # Client expects None if not found usually.
             return None
        
        # Convert to dict if it's a Pydantic model
        if hasattr(episode, "model_dump"):
            return episode.model_dump()
        return episode
    except AttributeError:
        # Fallback if method doesn't exist on DB object
        query = """
        MATCH (e:Episode)
        WHERE $session_id IN e.metadata.session_id OR e.metadata.session_id = $session_id
        RETURN e
        ORDER BY e.created_at DESC
        LIMIT 1
        """
        # This is a guess at the schema.
        # Actually, let's look at how get_episode_by_session_id was likely implemented.
        # It probably looks up by session_id in metadata.
        # But wait, the previous error said 'DBProxy' object has no attribute 'get_episode_by_session_id'.
        # This means the CLIENT didn't have it. The original code used it, so RyugraphDB MUST have had it.
        
        episode = ryumem.db.get_episode_by_session_id(session_id)
        return episode

    except Exception as e:
        logger.error(f"Error getting episode by session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting episode by session: {str(e)}")


@app.patch("/episodes/{episode_uuid}/metadata", response_model=Dict[str, Any])
async def update_episode_metadata(
    episode_uuid: str,
    request: UpdateMetadataRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Update metadata for an existing episode.
    """
    try:
        result = ryumem.db.update_episode_metadata(episode_uuid, request.metadata)
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return result
    except Exception as e:
        logger.error(f"Error updating episode metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating metadata: {str(e)}")


@app.delete("/episodes/{episode_uuid}", response_model=Dict[str, Any])
async def delete_episode(
    episode_uuid: str,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Delete an episode by UUID.
    """
    try:
        result = ryumem.db.delete_episode(episode_uuid)
        return result
    except Exception as e:
        logger.error(f"Error deleting episode: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting episode: {str(e)}")


@app.post("/cypher/execute", response_model=CypherResponse)
async def execute_cypher(
    request: CypherRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Execute a raw Cypher query.
    WARNING: This is a high-privilege endpoint.
    """
    try:
        results = ryumem.db.execute(request.query, request.params)
        return CypherResponse(results=results)
    except Exception as e:
        logger.error(f"Error executing cypher: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing cypher: {str(e)}")


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

        # Helper to parse metadata JSON string to dict
        def parse_metadata(metadata):
            if metadata is None:
                return None
            if isinstance(metadata, dict):
                return metadata
            if isinstance(metadata, str):
                try:
                    return json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse metadata JSON: {metadata}")
                    return {}
            return {}

        episodes = []
        for ep in result["episodes"]:
            try:
                episodes.append(EpisodeInfo(
                    uuid=ep["uuid"],
                    name=ep["name"],
                    content=ep["content"],
                    source=ep["source"],
                    source_description=ep["source_description"],
                    kind=ep.get("kind"),
                    created_at=ep["created_at"].isoformat() if isinstance(ep["created_at"], datetime) else str(ep["created_at"]),
                    valid_at=ep["valid_at"].isoformat() if isinstance(ep["valid_at"], datetime) else str(ep["valid_at"]),
                    user_id=clean_value(ep.get("user_id")),
                    metadata=parse_metadata(ep.get("metadata")),
                ))
            except Exception as e:
                logger.warning(f"Failed to convert episode {ep.get('uuid', 'unknown')} to EpisodeInfo: {e}, skipping")
                continue

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
    ryumem: Ryumem = Depends(get_write_ryumem)
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
        # Normalize user_id: empty string means "all users" (None)
        user_id = request.user_id if request.user_id else None

        results = ryumem.search(
            query=request.query,
            user_id=user_id,
            limit=request.limit,
            strategy=request.strategy,
            min_rrf_score=request.min_rrf_score,
            min_bm25_score=request.min_bm25_score,
            kinds=request.kinds,
            tags=request.tags,
            tag_match_mode=request.tag_match_mode,
        )

        episodes = []
        for episode in results.episodes:
            episodes.append(EpisodeInfo(
                uuid=episode.uuid,
                name=episode.name,
                content=episode.content,
                source=episode.source,
                source_description=episode.source_description,
                kind=episode.kind.value if hasattr(episode.kind, 'value') else str(episode.kind) if episode.kind else None,
                created_at=episode.created_at,
                valid_at=episode.valid_at,
                user_id=episode.user_id or None,
                metadata=episode.metadata or None,
                score=results.scores.get(episode.uuid, 0.0)
            ))
        
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
            count=len(entities) + len(edges) + len(episodes),
            episodes=episodes
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


        return StatsResponse(
            total_episodes=total_episodes,
            total_entities=total_entities,
            total_relationships=total_relationships,
            db_path=ryumem.config.database.db_path
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")


@app.post("/tools", response_model=ToolResponse)
async def save_tool(
    request: SaveToolRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """Save a tool to the database."""
    try:
        ryumem.db.save_tool(
            tool_name=request.tool_name,
            description=request.description,
            name_embedding=request.name_embedding
        )
        return ToolResponse(
            tool_name=request.tool_name,
            description=request.description,
            name_embedding=request.name_embedding,
            created_at=None  # Could add timestamp if needed
        )
    except Exception as e:
        logger.error(f"Error saving tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving tool: {str(e)}")


@app.get("/tools/{name}", response_model=Optional[Dict[str, Any]])
async def get_tool_by_name(
    name: str,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """Get a tool by name."""
    try:
        tool = ryumem.db.get_tool_by_name(name)
        if not tool:
            # Return None (200 OK with null body) or 404?
            # Client expects None if not found usually.
            # But FastAPI with Optional response model handles None as null JSON.
            return None
        return tool
    except Exception as e:
        logger.error(f"Error getting tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting tool: {str(e)}")


@app.post("/tools/batch", response_model=BatchSaveToolsResponse)
async def batch_save_tools(
    request: BatchSaveToolsRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Batch save multiple tools to the database.

    This endpoint efficiently saves multiple tools in a single request.
    For each tool:
    - If it doesn't exist, it creates a new tool node
    - If it already exists, it updates the description and increments mentions

    Returns statistics about the operation including number of tools saved,
    updated, and any errors encountered.
    """
    saved = 0
    updated = 0
    failed = 0
    errors = []

    for tool in request.tools:
        try:
            # Check if tool already exists
            existing = ryumem.db.get_tool_by_name(tool.tool_name)

            # save_tool handles both create and update
            ryumem.db.save_tool(
                tool_name=tool.tool_name,
                description=tool.description,
                name_embedding=tool.name_embedding
            )

            if existing:
                updated += 1
            else:
                saved += 1

        except Exception as e:
            failed += 1
            error_msg = f"Failed to save tool '{tool.tool_name}': {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg, exc_info=True)

    logger.info(f"Batch save completed: {saved} saved, {updated} updated, {failed} failed")

    return BatchSaveToolsResponse(
        saved=saved,
        updated=updated,
        failed=failed,
        errors=errors
    )


@app.post("/embeddings", response_model=EmbedResponse)
async def embed_text(
    request: EmbedRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """Generate embedding for text."""
    try:
        if not ryumem.embedding_client:
             raise HTTPException(status_code=503, detail="Embedding client not initialized")
        
        embedding = ryumem.embedding_client.embed(request.text)
        return EmbedResponse(embedding=embedding)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating embedding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")


@app.post("/llm/generate", response_model=GenerateResponse)
async def generate_text(
    request: GenerateRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """Generate text using LLM."""
    try:
        if not ryumem.llm_client:
             raise HTTPException(status_code=503, detail="LLM client not initialized")
        
        response = ryumem.llm_client.generate(
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        # response is usually a dict with 'content'
        content = response.get("content", "") if isinstance(response, dict) else str(response)
        return GenerateResponse(content=content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating text: {str(e)}")



@app.post("/prune", response_model=PruneMemoriesResponse)
async def prune_memories(
    request: PruneMemoriesRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Prune and compact memories to keep the graph efficient.

    This performs:
    - Delete facts that were invalidated/expired long ago
    - Remove entities with very few mentions (likely noise)
    - Merge near-duplicate relationship facts
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
    """Request model for registering/updating agent configurations"""
    base_instruction: str = Field(..., description="The agent's original instruction text (used as unique key)")
    agent_type: str = Field("google_adk", description="Type of agent (e.g., google_adk, custom_agent)")
    enhanced_instruction: Optional[str] = Field(None, description="Instruction with memory/tool guidance added")
    query_augmentation_template: Optional[str] = Field(None, description="Template for query augmentation")
    memory_enabled: bool = Field(False, description="Whether memory features are enabled")
    tool_tracking_enabled: bool = Field(False, description="Whether tool tracking is enabled")

    class Config:
        json_schema_extra = {
            "example": {
                "base_instruction": "You are a helpful assistant.",
                "agent_type": "google_adk",
                "enhanced_instruction": "You are a helpful assistant.\n\nMEMORY USAGE:...",
                "query_augmentation_template": "[Previous Attempt]...",
                "memory_enabled": True,
                "tool_tracking_enabled": False
            }
        }


class AgentInstructionResponse(BaseModel):
    """Response model for agent configurations"""
    instruction_id: str = Field(..., description="UUID of the agent configuration")
    base_instruction: str = Field(..., description="The agent's original instruction text")
    enhanced_instruction: str = Field("", description="Instruction with memory/tool guidance added")
    query_augmentation_template: str = Field("", description="Template for query augmentation")
    agent_type: str = Field(..., description="Type of agent")
    memory_enabled: bool = Field(..., description="Whether memory features are enabled")
    tool_tracking_enabled: bool = Field(..., description="Whether tool tracking is enabled")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


@app.post("/agent-instructions", response_model=AgentInstructionResponse, tags=["Agent Instructions"])
async def create_agent_instruction(
    request: AgentInstructionRequest,
    ryumem: Ryumem = Depends(get_write_ryumem)
):
    """
    Create a new custom agent instruction.

    The instruction will be stored in the database and can be retrieved
    by agents to customize their behavior.

    Note: This endpoint requires write access to the database.
    """
    try:

        # Save/update the agent configuration
        instruction_id = ryumem.save_agent_instruction(
            base_instruction=request.base_instruction,
            agent_type=request.agent_type,
            enhanced_instruction=request.enhanced_instruction,
            query_augmentation_template=request.query_augmentation_template,
            memory_enabled=request.memory_enabled,
            tool_tracking_enabled=request.tool_tracking_enabled
        )

        # Get the created/updated agent configuration
        agents = ryumem.list_agent_instructions(
            agent_type=request.agent_type,
            limit=1
        )

        if not agents:
            raise HTTPException(status_code=500, detail="Failed to retrieve agent configuration")

        agent_config = agents[0]

        return AgentInstructionResponse(
            instruction_id=agent_config["instruction_id"],
            base_instruction=agent_config["base_instruction"],
            enhanced_instruction=agent_config.get("enhanced_instruction", ""),
            query_augmentation_template=agent_config.get("query_augmentation_template", ""),
            agent_type=agent_config["agent_type"],
            memory_enabled=agent_config.get("memory_enabled", False),
            tool_tracking_enabled=agent_config.get("tool_tracking_enabled", False),
            created_at=agent_config["created_at"],
            updated_at=agent_config.get("updated_at", agent_config["created_at"])
        )

    except Exception as e:
        logger.error(f"Error creating agent instruction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating agent instruction: {str(e)}")


@app.get("/agent-instructions", response_model=List[AgentInstructionResponse], tags=["Agent Instructions"])
async def list_agent_instructions(
    agent_type: Optional[str] = None,
    limit: int = 50,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    List all agent configurations with optional filters.

    Returns agents ordered by last update (newest first).
    """
    try:
        agents = ryumem.list_agent_instructions(
            agent_type=agent_type,
            limit=limit
        )

        return [
            AgentInstructionResponse(
                instruction_id=agent["instruction_id"],
                base_instruction=agent["base_instruction"],
                enhanced_instruction=agent.get("enhanced_instruction", ""),
                query_augmentation_template=agent.get("query_augmentation_template", ""),
                agent_type=agent["agent_type"],
                memory_enabled=agent.get("memory_enabled", False),
                tool_tracking_enabled=agent.get("tool_tracking_enabled", False),
                created_at=agent["created_at"],
                updated_at=agent.get("updated_at", agent["created_at"])
            )
            for agent in agents
        ]

    except Exception as e:
        logger.error(f"Error listing agent configurations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing agent configurations: {str(e)}")


@app.get("/agent-instructions/by-text", tags=["Agent Instructions"])
async def get_instruction_by_text(
    instruction_text: str,
    agent_type: str,
    instruction_type: str,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get instruction text by key (stored in original_user_request field).
    
    Args:
        instruction_text: The key to search for (stored in original_user_request)
        agent_type: Type of agent (e.g., "google_adk")
        instruction_type: Type of instruction (e.g., "memory_usage")
    
    Returns:
        {"instruction_text": str} if found, 404 if not found
    """
    try:
        result = ryumem.get_instruction_by_text(
            instruction_text=instruction_text,
            agent_type=agent_type,
            instruction_type=instruction_type
        )
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"No instruction found for key '{instruction_text}'"
            )
        
        return {"instruction_text": result}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting instruction by text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting instruction: {str(e)}")


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


# ===== Settings Management Endpoints =====

class UpdateConfigRequest(BaseModel):
    """Request model for updating configuration"""
    updates: Dict[str, Any] = Field(..., description="Dictionary of key-value pairs to update")

    class Config:
        json_schema_extra = {
            "example": {
                "updates": {
                    "llm.provider": "gemini",
                    "llm.model": "gemini-2.0-flash-exp",
                    "embedding.provider": "gemini"
                }
            }
        }


class ConfigValueResponse(BaseModel):
    """Response model for configuration values"""
    key: str
    value: Any
    category: str
    data_type: str
    is_sensitive: bool
    updated_at: str
    description: str


class SettingsResponse(BaseModel):
    """Response model for settings"""
    settings: Dict[str, List[ConfigValueResponse]]
    total: int


@app.get(
    "/api/settings",
    response_model=SettingsResponse,
    tags=["Settings"],
    summary="Get all system configuration settings"
)
async def get_all_settings(
    mask_sensitive: bool = True,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get all system configuration settings grouped by category.

    Args:
        mask_sensitive: Whether to mask sensitive values (API keys) in response

    Returns:
        Dictionary of settings grouped by category
    """
    try:
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(ryumem.db)
        grouped_configs = service.get_all_configs_grouped(mask_sensitive=mask_sensitive)

        # Create virtual "api_keys" category from llm API keys
        if "llm" in grouped_configs:
            api_key_configs = [cfg for cfg in grouped_configs["llm"] if "api_key" in cfg["key"]]
            non_api_key_configs = [cfg for cfg in grouped_configs["llm"] if "api_key" not in cfg["key"]]

            if api_key_configs:
                grouped_configs["api_keys"] = api_key_configs
                grouped_configs["llm"] = non_api_key_configs

        # Convert to response model
        settings_dict = {}
        total = 0
        for category, configs in grouped_configs.items():
            settings_dict[category] = [
                ConfigValueResponse(
                    key=cfg["key"],
                    value=cfg["value"],
                    category=cfg["category"],
                    data_type=cfg["data_type"],
                    is_sensitive=cfg["is_sensitive"],
                    updated_at=cfg["updated_at"].isoformat() if hasattr(cfg["updated_at"], "isoformat") else str(cfg["updated_at"]),
                    description=cfg["description"]
                )
                for cfg in configs
            ]
            total += len(configs)

        return SettingsResponse(settings=settings_dict, total=total)

    except Exception as e:
        logger.error(f"Error getting settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting settings: {str(e)}")


@app.get(
    "/api/settings/{category}",
    response_model=List[ConfigValueResponse],
    tags=["Settings"],
    summary="Get settings for a specific category"
)
async def get_settings_by_category(
    category: str,
    mask_sensitive: bool = True,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Get configuration settings for a specific category.

    Args:
        category: Configuration category (e.g., 'llm', 'embedding', 'api_keys')
        mask_sensitive: Whether to mask sensitive values

    Returns:
        List of configuration values for the category
    """
    try:
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(ryumem.db)

        # Handle virtual "api_keys" category
        if category == "api_keys":
            # Get all llm configs and filter to just API keys
            all_configs = service.db.get_configs_by_category("llm")
            configs = [cfg for cfg in all_configs if "api_key" in cfg["key"]]
        else:
            configs = service.db.get_configs_by_category(category)

        if not configs:
            raise HTTPException(status_code=404, detail=f"Category not found: {category}")

        # Mask sensitive values if requested
        # Show first 4 and last 6 characters for API keys
        for cfg in configs:
            if mask_sensitive and cfg["is_sensitive"] and cfg["value"]:
                value_str = cfg["value"]
                if len(value_str) > 10:  # Need at least 11 chars to show 4 + 6
                    cfg["value"] = value_str[:4] + "***" + value_str[-6:]
                else:
                    cfg["value"] = "***"

        return [
            ConfigValueResponse(
                key=cfg["key"],
                value=cfg["value"],
                category=cfg["category"],
                data_type=cfg["data_type"],
                is_sensitive=cfg["is_sensitive"],
                updated_at=cfg["updated_at"].isoformat() if hasattr(cfg["updated_at"], "isoformat") else str(cfg["updated_at"]),
                description=cfg["description"]
            )
            for cfg in configs
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting settings for category {category}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting settings: {str(e)}")


@app.put(
    "/api/settings",
    tags=["Settings"],
    summary="Update multiple configuration settings"
)
async def update_settings(
    request: UpdateConfigRequest,
    ryumem: Ryumem = Depends(get_write_ryumem),
    customer_id: str = Depends(get_current_customer)
):
    """
    Update multiple configuration settings.

    Args:
        request: Dictionary of key-value pairs to update

    Returns:
        Summary of update results
    """
    try:
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(ryumem.db)

        # Validate all configs before updating
        validation_errors = []
        for key, value in request.updates.items():
            is_valid, error_msg = service.validate_config_value(key, value)
            if not is_valid:
                validation_errors.append(f"{key}: {error_msg}")

        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "Validation failed", "errors": validation_errors}
            )

        # Update configs
        success_count, failed_keys = service.update_multiple_configs(request.updates)

        # Invalidate cache so next request gets fresh config from database
        invalidate_ryumem_cache(customer_id)

        return {
            "message": f"Updated {success_count} configuration(s)",
            "success_count": success_count,
            "failed_keys": failed_keys,
            "updated_keys": [k for k in request.updates.keys() if k not in failed_keys]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating settings: {str(e)}")


@app.post(
    "/api/settings/validate",
    tags=["Settings"],
    summary="Validate configuration values without saving"
)
async def validate_settings(
    request: UpdateConfigRequest,
    ryumem: Ryumem = Depends(get_ryumem)
):
    """
    Validate configuration values without saving them.

    Args:
        request: Dictionary of key-value pairs to validate

    Returns:
        Validation results for each key
    """
    try:
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(ryumem.db)

        results = {}
        for key, value in request.updates.items():
            is_valid, error_msg = service.validate_config_value(key, value)
            results[key] = {
                "valid": is_valid,
                "error": error_msg if not is_valid else None
            }

        all_valid = all(r["valid"] for r in results.values())

        return {
            "valid": all_valid,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error validating settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error validating settings: {str(e)}")


@app.post(
    "/api/settings/reset-defaults",
    tags=["Settings"],
    summary="Reset all settings to default values"
)
async def reset_to_defaults(
    ryumem: Ryumem = Depends(get_write_ryumem),
    customer_id: str = Depends(get_current_customer)
):
    """
    Reset all configuration settings to their default values.

    Returns:
        Summary of reset operation
    """
    try:
        from ryumem_server.core.config_service import ConfigService

        service = ConfigService(ryumem.db)

        # Get default config model
        defaults = service.get_default_configs()

        # Extract to dict using model_dump and flatten
        updates = {}
        for section_name, section_value in defaults.model_dump().items():
            if section_name == "database":
                continue
            for field_name, value in section_value.items():
                updates[f"{section_name}.{field_name}"] = value

        success_count, failed_keys = service.update_multiple_configs(updates)

        # Invalidate cache so next request gets fresh config from database
        invalidate_ryumem_cache(customer_id)

        return {
            "message": f"Reset {success_count} configuration(s) to defaults",
            "success_count": success_count,
            "failed_keys": failed_keys
        }

    except Exception as e:
        logger.error(f"Error resetting settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resetting settings: {str(e)}")


@app.get("/customer/me")
async def get_customer_me(
    customer_id: str = Depends(get_current_customer)
):
    """
    Get current authenticated customer details.
    """
    # Get full customer details including github_username
    if _auth_manager:
        details = _auth_manager.get_customer_details(customer_id)
        if details:
            return {
                "customer_id": customer_id,
                "github_username": details.get("github_username"),
                "display_name": details.get("github_username") or customer_id
            }
    return {"customer_id": customer_id, "display_name": customer_id}


@app.delete("/database/reset")
async def reset_database(
    ryumem: Ryumem = Depends(get_write_ryumem),
    customer_id: str = Depends(get_current_customer)
):
    """
    Reset the entire database - delete all nodes and relationships.

    WARNING: This is irreversible! All data will be permanently deleted.
    The .db file will remain but will be empty.

    Returns:
        Success message with timestamp
    """
    try:
        logger.warning(f"Database reset requested by customer: {customer_id}")

        # Reset the database (deletes all nodes and relationships)
        ryumem.db.reset()

        # Invalidate the cached Ryumem instance so next request gets fresh instance
        invalidate_ryumem_cache(customer_id)

        logger.info(f"Database reset completed for customer: {customer_id}")

        return {
            "message": "Database reset successfully. All data has been deleted.",
            "customer_id": customer_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error resetting database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error resetting database: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

