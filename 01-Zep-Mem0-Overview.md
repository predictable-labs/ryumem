# Temporal Knowledge Graphs for AI Agent Memory

## Overview

This document provides a comprehensive overview of two cutting-edge approaches to building scalable, production-ready memory systems for AI agents: **Zep** and **Mem0**. Both systems address the fundamental challenge of enabling AI agents to maintain long-term, temporally-aware memory across multiple sessions.

---

## Executive Summary

### The Problem
Traditional RAG (Retrieval-Augmented Generation) systems work well for static document corpora but struggle with:
- Dynamic, evolving conversations and business data
- Temporal reasoning (tracking how facts change over time)
- Multi-session context maintenance
- Efficient retrieval with low latency
- Managing contradictory or outdated information

### The Solution
Both Zep and Mem0 introduce memory layers that:
- **Extract** relevant facts from ongoing interactions
- **Store** information with temporal awareness
- **Update** knowledge as facts change or become outdated
- **Retrieve** contextually relevant information efficiently

---

## 1. Zep: Temporal Knowledge Graph Architecture

### Paper Details
- **Title:** Zep: A Temporal Knowledge Graph Architecture for Agent Memory
- **Authors:** Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, Daniel Chalef (Zep AI)
- **arXiv ID:** 2501.13956
- **Published:** January 2025
- **PDF:** [Available on arXiv](https://arxiv.org/abs/2501.13956)
- **Code:** [getzep/graphiti on GitHub](https://github.com/getzep/graphiti)

### Core Innovation: Graphiti Engine

Zep's backbone is **Graphiti**, a temporally-aware knowledge graph engine that treats memory as a living, evolving graph rather than static documents.

#### Key Architecture Components

##### 1. Hierarchical Subgraphs
```
Episode Subgraph → Semantic/Entity Subgraph → Community/Summary Subgraph
     (raw events)      (entities + facts)         (high-level summaries)
```

- **Episode Subgraph:** Raw events (messages, texts, JSON changes) with timestamps
- **Semantic/Entity Subgraph:** Extracted entities, facts, and relationships
- **Community/Summary Subgraph:** Higher-level clusters and domain summaries

##### 2. Bi-Temporal Model
Each fact/edge contains **two time dimensions**:

| Dimension | Description |
|-----------|-------------|
| **Valid Time** | When the fact is true in the real world |
| **Ingestion/Transaction Time** | When the system ingested or updated the fact |

This enables queries like:
- "What was true at time T1?"
- "How has fact X changed since T0?"
- "When did we learn about fact Y?"

##### 3. Fact/Entity Extraction and Resolution

**Entity Processing:**
```python
entities = NER(episode_text)
for each entity:
    embedding = encode(entity)
    candidates = vector_search(embedding, entity_index)
    if cosine_similarity > θ_merge (≈0.85):
        merge_with_existing_entity(candidates)
    else:
        create_new_entity_node(entity)
```

**Fact Processing:**
```python
facts = extract_facts(episode_text, entities)
for each fact:
    edge = (subject, predicate, object)
    embedding = encode(fact_text)
    if similar_edge_exists(subject, object):
        invalidate(old_edge)
    insert(edge, embedding, valid_time, ingestion_time)
```

##### 4. Hybrid Retrieval Pipeline

When an agent queries memory:
```python
# Multi-modal search
semantic_hits = vector_search(query, episode_index)
keyword_hits = bm25_search(query)
graph_hits = graph_traversal(query_related_entities)

# Reranking with temporal decay
results = rerank(
    semantic_hits ∪ keyword_hits ∪ graph_hits,
    scoring=hybrid_score(temporal_decay, recency, relevance)
)
```

### Performance Benchmarks

#### Deep Memory Retrieval (DMR)
- **Zep:** 94.8% accuracy
- **MemGPT baseline:** 93.4% accuracy
- **Improvement:** +1.4% absolute

#### LongMemEval (Multi-session, Temporal Reasoning)
- **Accuracy improvement:** Up to +18.5%
- **Latency reduction:** ~90%
- **Use cases:** Enterprise-style temporal reasoning, cross-session context

### Technical Implementation
- **Graph backend:** Rust (Graphiti)
- **Embeddings:** 1024-dim (OpenAI text-embedding-3-large default)
- **Vector index:** HNSW
- **APIs:** gRPC + REST

### Community Adoption
- **GitHub stars:** ~14,000 (in 8 months)
- **Contributors:** 35+
- **PyPI downloads:** 25,000 weekly

---

## 2. Mem0: Production-Ready AI Agent Memory

### Paper Details
- **Title:** Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory
- **Authors:** Chhikara et al.
- **arXiv ID:** 2504.19413
- **Published:** April 2025
- **Website:** [mem0.ai](https://mem0.ai/)
- **Code:** [mem0ai/mem0 on GitHub](https://github.com/mem0ai/mem0)

### Core Innovation: Memory-Centric Pipeline

Mem0 focuses on **extraction, consolidation, and dynamic update** of conversational facts.

#### Architecture Variants

##### 1. Mem0 (Base)
Simple memory extraction and update pipeline:

**Extraction Phase:**
```
Input: [conversation_summary, recent_messages, new_message_pair]
↓
LLM extracts candidate memory facts
↓
Output: ["User prefers X", "Project milestone Y reached", ...]
```

**Update Phase:**
```
For each candidate fact:
    1. Retrieve semantically similar existing memories (vector search)
    2. LLM classifies operation:
       - ADD (new memory)
       - UPDATE (refine/replace existing)
       - DELETE (remove contradictory/outdated)
       - NOOP (ignore)
    3. Apply operation to memory store
```

##### 2. Mem0ᵍ (Graph Variant)
Represents memory as a **directed labeled graph** G = (V, E, L):
- **Nodes (V):** Entities (people, objects, topics)
- **Edges (E):** Relationships
- **Labels (L):** Semantic types

**Retrieval Modes:**
1. **Entity-centric:** Identify key entities → traverse adjacent nodes/edges
2. **Semantic triplet:** Encode query → match against relationship triplets

**Historical Preservation:**
- Old edges marked obsolete (not deleted)
- Preserves historical context

#### Retrieval in Agent Pipeline
```
User Query
↓
Retrieve relevant memories (vector search + graph traversal for Mem0ᵍ)
↓
Combine with recent context
↓
Supply to LLM as prompt
```

### Performance Benchmarks

#### LOCOMO Benchmark (Long Conversation, Multi-Session)
- **Accuracy improvement:** +26% vs OpenAI memory baseline
- **Latency reduction:** 91% lower p95 latency vs full-context approach
- **Token savings:** 90% fewer tokens

#### Mem0ᵍ (Graph Variant)
- **Additional accuracy boost:** +2% over base Mem0
- **Trade-off:** Modest latency increase

#### Token Footprint
- **Mem0:** ~7k tokens per conversation
- **Mem0ᵍ:** ~14k tokens per conversation
- **Comparison:** Far less than full-context systems

### Business Traction

#### Funding & Growth (2025)
- **Funding:** $24M (Seed + Series A)
- **GitHub stars:** 41,000
- **Python downloads:** 14 million
- **API calls:** 35M (Q1) → 186M (Q3 2025)

#### Enterprise Adoption
- **AWS Partnership:** Exclusive AI memory provider for AWS Agent SDK
- **Integration:** 3 lines of code
- **Frameworks:** CrewAI, Flowise, Langflow
- **Compliance:** SOC 2, HIPAA, BYOK (Bring Your Own Key)

---

## Comparison: Zep vs Mem0

| Aspect | Zep (Graphiti) | Mem0 |
|--------|----------------|------|
| **Core Approach** | Temporal knowledge graph | Memory extraction + consolidation |
| **Temporal Model** | Bi-temporal (valid time + ingestion time) | Update operations (ADD/UPDATE/DELETE) |
| **Graph Structure** | Hierarchical subgraphs (episode → entity → summary) | Optional graph variant (Mem0ᵍ) |
| **Retrieval** | Hybrid (semantic + BM25 + graph traversal) | Semantic + graph (in Mem0ᵍ) |
| **Primary Focus** | Temporal reasoning, historical context | Production deployment, efficiency |
| **Benchmarks** | DMR: 94.8%, LongMemEval: +18.5% accuracy, 90% latency reduction | LOCOMO: +26% accuracy, 91% latency reduction, 90% token savings |
| **Implementation** | Rust (backend), Python SDK | Python-first |
| **Vector Index** | HNSW | Configurable |
| **Enterprise Focus** | Knowledge evolution, compliance | AWS integration, SOC2/HIPAA |
| **Community** | 14k stars, 25k weekly PyPI downloads | 41k stars, 14M total downloads |

---

## Key Takeaways

### When to Choose Zep
- Need precise temporal reasoning ("what changed when")
- Compliance/audit requirements demand historical tracking
- Complex enterprise data with evolving relationships
- Building knowledge-intensive agents (research, legal, healthcare)

### When to Choose Mem0
- Rapid deployment (3 lines of code integration)
- AWS ecosystem integration required
- Priority on production stability and compliance
- Need extreme efficiency (low latency, token savings)

### Hybrid Approach
Many production systems could benefit from combining ideas:
- Use Mem0's extraction/update pipeline for efficiency
- Add Zep's bi-temporal model for historical accuracy
- Implement hybrid retrieval (semantic + graph + keyword)
- Leverage HNSW for vector search in both systems

---

## Market Context

### AI Agent Memory Market (2025)
- **Market size:** $7.38B (2025) → $103.6B (2032)
- **Enterprise adoption:** 85% have implemented or plan to deploy AI agents
- **Agentic AI market:** $5.2B (2024) → $196.6B (2034) @ 43.8% CAGR

### AI-Driven Knowledge Management
- **Market size:** $3.0B (2024) → $102.1B (2034) @ 42.3% CAGR
- **Primary use cases:** Business process automation (64% of deployments)
- **Key drivers:** Reduce time-to-insight, elevate productivity

### Critical Industries
- Healthcare
- Financial Services
- Pharmaceuticals
- Legal
- Consumer Goods

Where temporal accuracy is critical for compliance and decision-making.

---

## References

1. Rasmussen, P. et al. (2025). "Zep: A Temporal Knowledge Graph Architecture for Agent Memory." arXiv:2501.13956
2. Chhikara et al. (2025). "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory." arXiv:2504.19413
3. GitHub: [getzep/graphiti](https://github.com/getzep/graphiti)
4. GitHub: [mem0ai/mem0](https://github.com/mem0ai/mem0)
5. Zep Blog: [Graphiti: Knowledge Graphs for Agents](https://blog.getzep.com/graphiti-knowledge-graphs-for-agents/)
6. Mem0 Research: [mem0.ai/research](https://mem0.ai/research)
