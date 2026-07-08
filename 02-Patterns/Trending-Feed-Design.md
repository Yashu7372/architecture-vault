# Trending Feed Design

## Goal

Understand how trending topics/posts are detected and injected into a home timeline without breaking the main following feed.

---

## 1. What is Trending?

A trending item is content that is receiving unusually high activity in a short time window.

Signals can include:

- Likes
- Replies
- Reposts
- Views
- Shares
- Clicks
- Hashtag usage
- Location-based activity
- Sudden velocity increase

Trending is not only total count. A post with 1 million old likes may not be trending. A post with 5,000 interactions in 5 minutes may be trending.

---

## 2. Basic Architecture

```text
User Events
  likes/replies/views/shares
        |
        v
Kafka / Event Bus
        |
        v
Stream Processor
        |
        v
Trending Score Store
        |
        v
Trending Service
        |
        v
Timeline Service injects trending items
```

---

## 3. Window-Based Aggregation

Trending should be calculated using time windows.

Examples:

```text
1 minute window
5 minute window
15 minute window
1 hour window
24 hour window
```

A simple counter key can be:

```text
trend:post:{postId}:window:5m
trend:hashtag:{tag}:window:15m
trend:region:{region}:window:1h
```

---

## 4. Simple Trending Score

A simple learning formula:

```text
trendingScore = recentEngagement / ageInMinutes
```

Better formula:

```text
trendingScore =
  (likes * 1) +
  (replies * 3) +
  (reposts * 4) +
  (views * 0.1) +
  velocityBoost -
  agePenalty
```

---

## 5. Velocity-Based Detection

Trending means activity is increasing faster than normal.

```text
velocity = currentWindowCount - previousWindowCount
```

Example:

```text
Previous 5 min: 100 interactions
Current 5 min: 900 interactions
Velocity: +800
```

This item may be trending even if total engagement is not huge yet.

---

## 6. Trending Feed Injection

Timeline Service should not fully depend on Trending Service.

Safe flow:

```text
1. Load following timeline.
2. Load trending candidates with timeout.
3. Deduplicate by postId.
4. Apply ranking/safety filters.
5. Inject 1 trending item after every N normal items.
6. Return response.
```

Example layout:

```text
Following post
Following post
Trending post
Following post
Following post
Recommended post
```

---

## 7. Failure Handling

| Failure | Expected Behavior |
|---|---|
| Trending service slow | Return normal following feed |
| Trending store down | Skip trending injection |
| Duplicate trending post | Remove duplicate |
| Unsafe content | Filter before injection |
| Region unavailable | Use global trending fallback |

---

## 8. Java/Spring Boot Design

Services:

```text
engagement-service
trending-processor
trending-service
timeline-service
```

Event example:

```json
{
  "eventType": "POST_LIKED",
  "postId": "p901",
  "userId": "u100",
  "region": "DXB",
  "createdAt": "2026-07-08T10:00:00Z"
}
```

Trending API:

```http
GET /api/v1/trending/posts?region=DXB&limit=10
```

Response:

```json
{
  "items": [
    {
      "postId": "p901",
      "score": 982.5,
      "reason": "High engagement in last 5 minutes"
    }
  ]
}
```

---

## 9. Stream Processor Pseudocode

```java
public void handleEngagementEvent(EngagementEvent event) {
    String key = "trend:post:" + event.postId() + ":5m";
    counterStore.increment(key);
    counterStore.expire(key, Duration.ofMinutes(10));
}
```

A scheduled job or stream processor can periodically calculate top items:

```java
public List<TrendingItem> calculateTopTrending(String region) {
    return counterStore.topN("trend:region:" + region, 100);
}
```

---

## 10. DNBMS Mapping

Trending is similar to operational alert detection.

| Social Trending | DNBMS Operational Equivalent |
|---|---|
| Sudden likes/replies | Sudden baggage exceptions |
| Hot hashtag | Flight/ULD with abnormal activity |
| Regional trend | Station/terminal-specific alert |
| Trending score | Alert severity score |
| Feed injection | UI priority card/notification |

Example:

```text
If offload events for one flight cross threshold in 5 minutes,
show that flight as high-priority operational alert.
```

---

## 11. Key Learning

Trending is a stream aggregation problem. It should be built as a separate service and injected into the feed with timeout/fallback so the main feed remains reliable.
