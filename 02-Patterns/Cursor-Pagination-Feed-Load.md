# Cursor Pagination and Feed Load Design

## Goal

Design stable pagination for timeline/feed APIs. This avoids duplicates, missing records, and slow offset-based queries.

---

## 1. Why Offset Pagination Fails for Feeds

Offset pagination looks simple:

```http
GET /timeline?offset=20&limit=20
```

Problem: feeds keep changing while the user scrolls.

Example:

```text
1. User loads first 20 posts.
2. New posts arrive at the top.
3. User asks offset=20.
4. Some posts shift down.
5. User may see duplicates or miss posts.
```

Offset also becomes slow for large datasets because the database/cache must skip many rows.

---

## 2. Cursor Pagination

Cursor pagination uses the last seen item as the next page boundary.

```http
GET /timeline?limit=20
GET /timeline?cursor=eyJsYXN0U2NvcmUiOjk4MCwibGFzdENyZWF0ZWRBdCI6Ii4uLiIsImxhc3RQb3N0SWQiOjEyM30=&limit=20
```

The cursor usually contains:

```json
{
  "lastScore": 980,
  "lastCreatedAt": "2026-07-08T10:00:00Z",
  "lastPostId": 123,
  "direction": "OLDER"
}
```

Encode it as Base64 or signed token so the client does not modify it.

---

## 3. Feed Load API Shape

```http
GET /api/v1/timeline/home?limit=20
GET /api/v1/timeline/home?cursor={cursor}&limit=20
```

Response:

```json
{
  "items": [
    {
      "postId": "p901",
      "authorId": "u45",
      "text": "...",
      "createdAt": "2026-07-08T10:00:00Z",
      "sourceType": "FOLLOWING"
    }
  ],
  "nextCursor": "...",
  "hasMore": true
}
```

---

## 4. Sorting Rule

Use deterministic ordering.

Common order:

```text
ORDER BY score DESC, createdAt DESC, postId DESC
```

The cursor must include all fields used in ordering.

If two posts have the same score and time, `postId` becomes the tie breaker.

---

## 5. Query Logic

For older page:

```sql
SELECT *
FROM timeline_items
WHERE user_id = :userId
  AND (
       score < :lastScore
       OR (score = :lastScore AND created_at < :lastCreatedAt)
       OR (score = :lastScore AND created_at = :lastCreatedAt AND post_id < :lastPostId)
  )
ORDER BY score DESC, created_at DESC, post_id DESC
FETCH FIRST :limit ROWS ONLY;
```

This avoids offset and makes pagination stable.

---

## 6. Refresh for Newer Posts

For pull-to-refresh, use a newer-than cursor.

```http
GET /api/v1/timeline/home/newer?sinceCursor={topCursor}
```

Logic:

```text
Return items that are newer than the top item currently visible to the user.
```

This supports:

- Pull to refresh
- "New posts available" banner
- SSE/WebSocket push hint

---

## 7. Duplicate Prevention

Client should maintain a small set of already rendered post IDs.

Server should also deduplicate after merging:

```text
following feed + celebrity pull + trending + recommended
```

Dedup key:

```text
postId
```

---

## 8. Cursor Token Design

Good cursor fields:

```json
{
  "userId": "u100",
  "lastScore": 980,
  "lastCreatedAt": "2026-07-08T10:00:00Z",
  "lastPostId": "p123",
  "pageSize": 20,
  "issuedAt": "2026-07-08T10:10:00Z"
}
```

Production improvement:

- Sign the cursor with HMAC.
- Add expiry.
- Do not expose internal database IDs if sensitive.

---

## 9. Java DTO Example

```java
public record TimelineResponse(
    List<TimelineItemDto> items,
    String nextCursor,
    boolean hasMore
) {}

public record TimelineCursor(
    long lastScore,
    Instant lastCreatedAt,
    String lastPostId,
    String direction
) {}
```

---

## 10. Spring Boot Controller Example

```java
@GetMapping("/api/v1/timeline/home")
public TimelineResponse getHomeTimeline(
        @RequestParam(required = false) String cursor,
        @RequestParam(defaultValue = "20") int limit) {
    return timelineService.loadHomeTimeline(cursor, limit);
}
```

---

## 11. DNBMS Mapping

Feed cursor pagination maps well to operational dashboards.

Example:

```http
GET /api/v1/flights/{flightId}/events?cursor=...&limit=50
```

Use cursor fields:

```text
eventTime DESC, eventSequence DESC, eventId DESC
```

This avoids loading huge operational event history repeatedly and supports stable scrolling.

---

## 12. Key Learning

For feeds and event streams, avoid offset pagination. Use cursor/keyset pagination with a deterministic sort order and a tie breaker.
