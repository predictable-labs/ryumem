# ADR-001: Entity Extraction Status Tracking

## Status
Proposed

## Context

With the introduction of background entity extraction (see ADR-002), we need a way to track the extraction status for each episode. This enables:

1. **User visibility**: Users can see which episodes have been processed and which are pending
2. **Debugging**: When extraction fails, we can identify problematic episodes
3. **Dashboard features**: The UI can show extraction progress and results
4. **Retry logic**: Failed extractions can be identified and retried

### Options Considered

1. **Episode metadata field** - Store status in `episode.metadata.extraction_status`
2. **Separate status table** - New `ExtractionStatus` node in Ryugraph
3. **Redis-only tracking** - Status lives only in Redis job results

## Decision

Use **Episode metadata field** approach.

Add the following fields to episode metadata:

```json
{
  "extraction_status": "pending" | "processing" | "completed" | "failed",
  "extraction_job_id": "uuid-reference-to-redis-job",
  "extraction_completed_at": "2024-12-15T10:30:00Z",
  "extraction_entities_count": 5,
  "extraction_relationships_count": 3,
  "extraction_error": "Error message if failed"
}
```

## Rationale

### Why Episode Metadata?

1. **No schema changes required** - Metadata is already a JSON field, so we can add new keys without database migration
2. **Natural data ownership** - Episode is the parent of extraction results, so status belongs there
3. **Easy querying** - Existing episode queries can include extraction status
4. **Persistence** - Status persists after Redis job expires (jobs have 24hr TTL)
5. **Simplicity** - No new tables or relationships to manage

### Why Not Separate Table?

- Adds complexity with additional node type and relationships
- Requires joining data for common queries
- Overkill for simple status tracking

### Why Not Redis-Only?

- Jobs expire after 24 hours
- Harder to query historical data
- No persistence across Redis restarts (if not configured for persistence)

## Consequences

### Positive

- Status is immediately visible when fetching episode data
- No additional database queries needed for status
- Easy to extend with more metadata fields in future
- Works with existing caching and multi-tenancy

### Negative

- Episode metadata grows slightly larger (~100-200 bytes per episode)
- Need to handle concurrent updates to episode metadata carefully
- Worker must make HTTP call to update status (already needed for other updates)

### Dashboard Integration

The dashboard can:
- Show extraction status badge on episode cards
- Filter episodes by extraction status
- Display extraction statistics (entities/relationships count)
- Show error details for failed extractions

## Implementation Notes

1. When episode is created with `extract_entities=True`:
   - Set `extraction_status = "pending"`
   - Set `extraction_job_id = <job_id>`

2. When worker picks up job:
   - Status remains "pending" (or could update to "processing" if needed)

3. When extraction completes:
   - Worker calls `POST /internal/episodes/{id}/extraction-complete`
   - Updates all status fields

4. Error handling:
   - If extraction fails after max retries, status = "failed" with error message
   - Failed episodes can be retried manually via new endpoint (future)
