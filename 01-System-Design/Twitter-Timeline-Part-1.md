# Twitter Timeline System Design - Part 1

## Goal

Design a home timeline like Twitter/X: show recent and relevant posts from people a user follows, plus ranking, cursor pagination, feed refresh, and trending/recommended inserts.

This same pattern is useful for enterprise dashboards also: user subscribes to flights/ULDs, events arrive, projections are updated, and the UI loads a fast view.

---

## 1. Problem Statement

A user follows many authors. Each author posts at a different rate. The system must build a feed that is fast, fresh, ranked, and reliable.

Important challenges:

- High read traffic compared to writes.
- Celebrity users with millions of followers.
- Avoid duplicate posts during pagination.
- Support refresh for newer posts.
- Mix following feed with trending/recommended items.
- Keep feed available even if ranking/trending service is slow.

---

## 2. Functional Requirements

- User can create a post.
- User can follow/unfollow another user.
- User can load home timeline.
- User can paginate older timeline items.
- User can refresh for newer items.
- System can inject trending/recommended posts.

## 3. Non-Functional Requirements

- Low latency feed load.
- High availability.
- Eventual consistency is acceptable.
- Duplicate feed items should be avoided.
- Timeline read should not depend on heavy joins.
- Ranking failure should not break the base timeline.

---

## 4. Core Entities

```text
User
- userId
- name
- status

Follow
- followerId
- followeeId
- createdAt

Post
- postId
- authorId
- text/media
- createdAt
- visibility

TimelineItem
- userId
- postId
- authorId
- score
- createdAt
- sourceType: FOLLOWING | TRENDING | RECOMMENDED | AD
```

---

## 5. High-Level Architecture

```text
Mobile/Web Client
      |
      v
API Gateway
      |
      +--> Post Service ---------> Post DB
      |        |
      |        v
      |   Kafka / Event Bus
      |        |
      |        v
      |   Timeline Fanout Workers
      |        |
      |        v
      |   Timeline Store / Redis / Cassandra
      |
      +--> Timeline Service
               |
               +--> Timeline Cache
               +--> Ranking Service
               +--> Trending Service
               +--> Post Hydration Service
```

---

## 6. Post Creation Flow

```text
1. User creates a post.
2. Post Service validates and stores the post.
3. PostCreated event is published to Kafka/Event Bus.
4. Fanout workers consume the event.
5. Workers find followers of the author.
6. Timeline references are written into followers' timeline store.
7. When followers open the app, timeline loads quickly from prepared data.
```

---

## 7. Timeline Read Flow

```text
1. User opens home timeline.
2. Timeline Service reads precomputed timeline item IDs.
3. Timeline Service fetches post/user/media details.
4. Ranking Service reorders or filters items.
5. Trending/recommended items may be injected.
6. API returns items plus next cursor.
```

---

## 8. Fanout-on-Write

In fanout-on-write, when a user posts, the system pushes that post into the timeline inbox of all followers.

```text
Author A posts P1.
A has followers U1, U2, U3.
System writes P1 into:
- timeline:U1
- timeline:U2
- timeline:U3
```

Advantages:

- Very fast timeline read.
- Good for normal users.
- Read path is simple.

Disadvantages:

- Expensive for celebrities.
- Write amplification is high.
- Fanout job failure can create missing timeline entries.

---

## 9. Fanout-on-Read

In fanout-on-read, timeline is generated when the user opens the app.

```text
1. Get all users followed by current user.
2. Fetch recent posts from those users.
3. Merge, rank, and return.
```

Advantages:

- Cheaper writes.
- Good for celebrity accounts.
- No need to push to millions of follower timelines.

Disadvantages:

- Slow if user follows many people.
- Expensive read path.
- Requires efficient merge/ranking logic.

---

## 10. Hybrid Fanout Strategy

Real systems usually use a hybrid model.

```text
Normal users      -> fanout-on-write
Celebrity users   -> fanout-on-read
Trending content  -> injected during read
Recommended posts -> injected during read/ranking
```

This avoids writing celebrity posts to millions of timelines while keeping normal timeline reads fast.

---

## 11. Timeline Storage Model

Store lightweight references in timeline storage. Do not store full post JSON.

```text
Key: timeline:{userId}
Value: sorted list

[
  { postId: 901, authorId: 45, score: 982, createdAt: "2026-07-08T10:00:00Z" },
  { postId: 899, authorId: 88, score: 970, createdAt: "2026-07-08T09:59:00Z" }
]
```

Full post details are fetched later from Post Service/Post Cache. This is called hydration.

---

## 12. Ranking

Timeline ranking can use:

- Recency
- Author relationship strength
- Likes/replies/reposts
- User interest signals
- Post quality score
- Media type
- Diversity rules
- Safety/moderation rules

Simple learning score:

```text
score = freshnessScore + engagementScore + relationshipScore + qualityScore
```

For MVP, start chronological. Add ranking after the basic feed is stable.

---

## 13. Failure Scenarios

| Failure | Impact | Handling |
|---|---|---|
| Kafka down | New posts not fanned out | Retry/outbox |
| Fanout worker down | Missing timeline entries | Replay events |
| Redis down | Slow feed load | Fallback timeline DB |
| Ranking service slow | Feed delay | Return chronological feed |
| Trending service down | No trending section | Skip trending injection |
| Post hydration fails | Broken item | Drop item or return partial response |

---

## 14. Java/Spring Boot MVP

Services:

```text
post-service
follow-service
timeline-service
ranking-service
trending-service
notification-service
```

Tech stack:

```text
Spring Boot 3
Kafka or Solace
Redis or Couchbase
PostgreSQL/Oracle
React
Docker
OpenTelemetry
```

MVP implementation sequence:

```text
1. Create user
2. Follow user
3. Create post
4. Publish PostCreated event
5. Fanout to followers
6. Load home timeline
7. Cursor paginate timeline
```

---

## 15. Enterprise Mapping

| Twitter Feed | Enterprise/DNBMS Equivalent |
|---|---|
| User follows authors | User/role subscribes to flights/ULDs |
| Post event | Bag/flight/ULD operational event |
| Timeline inbox | UI projection per user/role/flight |
| Fanout worker | Solace consumer/projection updater |
| Redis timeline cache | Couchbase operational projection |
| Feed refresh | SSE changed-flight update |
| Trending | Alert/high-priority operational events |

---

## 16. Key Learning

The main architecture decision is:

> Should the feed be prepared when content is written, or generated when the user reads?

Most production systems use both.
