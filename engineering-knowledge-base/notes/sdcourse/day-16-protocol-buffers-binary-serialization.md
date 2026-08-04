# Day 16 — Protocol Buffers for Efficient Binary Serialization

## Course position

- Module 1: Foundations of Log Processing
- Week 3: Data Serialization and Formats
- Previous: Day 15 — JSON support for structured log data
- Current: Day 16 — Protocol Buffers for efficient binary serialization
- Next: Day 17 — Avro serialization and schema evolution

---

# 1. Public source material

## What was actually visible

The publicly accessible SDCourse curriculum lists Day 16 as:

> Implement Protocol Buffers for efficient binary serialization.

The publicly visible expected output is:

> Log system using Protocol Buffers with measurable performance gain.

The same public curriculum places Day 16 in Week 3, “Data Serialization and Formats,” immediately after Day 15 JSON support and before Day 17 Avro schema evolution.

Public source:

- https://sdcourse.substack.com/p/hands-on-distributed-systems-with

At the time this lesson was written, the public curriculum entry exposed the title, sequence, and expected outcome. No complete subscriber-only Day 16 article implementation, hidden prose, or inaccessible diagrams are reproduced here.

Everything below is an original Java 21 and Spring Boot lesson that teaches the topic independently.

---

# 2. Original standalone lesson

## 2.1 Why binary serialization matters

Day 15 introduced JSON as a human-readable structured format. JSON is excellent for interoperability and debugging, but its field names and textual values are repeated in every message.

A JSON log might look like this:

```json
{
  "eventId": "018f41d6-6d8a-7e60-b5df-c920ec77e98e",
  "occurredAtEpochMillis": 1785588932417,
  "level": "ERROR",
  "service": "payment-service",
  "eventType": "payment.failed",
  "message": "Authorization timed out",
  "traceId": "d84f04d8c26743c4b42b64f0e83de4a9"
}
```

Every message repeats strings such as `eventId`, `occurredAtEpochMillis`, `service`, and `eventType`. Numbers are represented as text digits. Parsers must tokenize text, compare field names, allocate strings, and convert values.

Protocol Buffers, commonly called Protobuf, defines the contract once in a `.proto` schema and transmits compact field identifiers and binary values.

The goal is not simply “smaller JSON.” The goal is a strongly defined, language-neutral binary contract with generated code and controlled compatibility rules.

## 2.2 First principles

Serialization converts an in-memory object into bytes.

Deserialization reconstructs a logical object from those bytes.

```text
Java object -> serializer -> byte sequence -> network/storage
byte sequence -> deserializer -> Java object
```

A useful serialization format must answer four questions:

1. How is each field identified?
2. How is each value encoded?
3. How does the receiver know the expected type?
4. What happens when producers and consumers use different schema versions?

JSON transmits field names and values directly. Protobuf transmits numeric field tags and encoded values while both sides share the schema.

For example:

```proto
string service = 4;
```

The number `4` is the permanent wire identity of the field. The name `service` is mainly used by generated source code and tooling.

## 2.3 Why the concept matters

A high-volume logging system can process millions of events per second. Serialization affects:

- network bandwidth
- Kafka or broker storage
- CPU time
- garbage collection
- request latency
- cache efficiency
- persistence size
- cross-language interoperability

Suppose one million JSON events average 700 bytes each. That is about 700 MB before compression. If an equivalent Protobuf payload averages 220 bytes, the same logical events require about 220 MB.

The exact gain depends on the data. The correct objective is therefore measurable improvement, not an assumed percentage.

## 2.4 Terminology

### Schema

The `.proto` file that defines messages, fields, types, enumerations, and services.

### Message

A structured Protobuf data type, similar to an immutable data-transfer object.

### Field number or tag

The numeric wire identifier assigned to a field. It must remain stable after release.

### Wire type

The low-level encoding category used for a value, such as varint, fixed-width integer, or length-delimited bytes.

### Varint

A variable-length integer encoding. Small values use fewer bytes than large values.

### Generated code

Language-specific classes produced by the Protobuf compiler from `.proto` schemas.

### Unknown field

A field present in incoming bytes but not recognized by the consumer’s current schema. Modern Protobuf implementations preserve or safely skip unknown fields, supporting compatible evolution.

### Reserved field

A removed field number or name declared as unavailable so it cannot accidentally be reused.

### Envelope

A stable outer message carrying metadata such as schema version, compression, tenant, source, and the encoded business payload.

## 2.5 Requirements

The Day 16 implementation should satisfy these functional requirements:

1. Accept structured log events through an API or transport adapter.
2. Convert the canonical Java model into Protobuf bytes.
3. Decode Protobuf bytes back into the canonical model.
4. validate required business invariants after decoding.
5. Reject malformed or unsupported payloads safely.
6. Measure payload size, encode time, decode time, and end-to-end throughput.
7. preserve event and batch identifiers across serialization.
8. support at least one compatible schema change.

Non-functional requirements:

- bounded memory usage
- thread-safe codecs
- deterministic error handling
- backward-compatible schema evolution
- observable performance
- transport-independent serialization
- protection against oversized and malicious inputs

## 2.6 Architecture

```mermaid
flowchart LR
    A[Log Producer] --> B[Canonical LogEvent]
    B --> C[Protobuf Mapper]
    C --> D[Generated Protobuf Message]
    D --> E[Binary Encoder]
    E --> F[Batching / Compression / TLS]
    F --> G[Transport or Broker]
    G --> H[Frame Decoder]
    H --> I[Protobuf Parser]
    I --> J[Generated Protobuf Message]
    J --> K[Domain Mapper]
    K --> L[Validation]
    L --> M[Idempotency Check]
    M --> N[Durable Storage]
    N --> O[Application ACK]
```

The serialization layer must remain separate from transport and storage.

A TCP server should not contain business mapping logic. A repository should not know whether the incoming event was JSON or Protobuf.

## 2.7 Component responsibilities

### Canonical domain model

Represents the application’s internal meaning independent of wire format.

```java
public record LogEvent(
        UUID eventId,
        Instant occurredAt,
        LogLevel level,
        String service,
        String eventType,
        String message,
        String traceId,
        Map<String, String> attributes
) {}
```

### Protobuf schema

Defines the public binary contract and stable field numbers.

### Generated message classes

Provide builders, parsers, enum types, and binary encoding generated by `protoc`.

### Mapper

Converts between `LogEvent` and the generated `LogEventProto` message.

### Codec

Owns byte encoding and decoding. It does not perform persistence or acknowledgements.

### Framing layer

Defines where one binary message or batch ends and the next begins on a byte stream.

### Validator

Checks semantic rules not fully expressible in Protobuf types.

### Idempotency service

Prevents duplicate durable effects when the same event or batch is retried.

### Repository or sink

Commits accepted events to durable storage.

### Metrics recorder

Measures serialization size, duration, failures, throughput, and compatibility errors.

## 2.8 Contract and data model

Create `src/main/proto/log_event.proto`:

```proto
syntax = "proto3";

package sdcourse.logging.v1;

option java_package = "com.example.logging.proto.v1";
option java_multiple_files = true;
option java_outer_classname = "LogEventSchema";

import "google/protobuf/timestamp.proto";

message LogEventProto {
  string event_id = 1;
  google.protobuf.Timestamp occurred_at = 2;
  LogLevelProto level = 3;
  string service = 4;
  string event_type = 5;
  string message = 6;
  string trace_id = 7;
  map<string, string> attributes = 8;
}

enum LogLevelProto {
  LOG_LEVEL_UNSPECIFIED = 0;
  TRACE = 1;
  DEBUG = 2;
  INFO = 3;
  WARN = 4;
  ERROR = 5;
  FATAL = 6;
}

message LogBatchProto {
  string batch_id = 1;
  repeated LogEventProto events = 2;
  int64 created_at_epoch_millis = 3;
  string producer_id = 4;
}
```

Important contract rules:

- Never change the meaning of an existing field number.
- Never reuse a removed field number.
- Add new optional-compatible fields using new numbers.
- Keep enum zero as an unspecified or unknown value.
- Avoid relying on field presence when ordinary proto3 scalar defaults are sufficient.
- Use wrapper types or `optional` when presence has business meaning.

If field 7 is removed later:

```proto
message LogEventProto {
  reserved 7;
  reserved "trace_id";
  // remaining fields
}
```

## 2.9 Maven configuration

A Spring Boot Java 21 project needs the Protobuf runtime and code-generation plugin.

```xml
<properties>
    <java.version>21</java.version>
    <protobuf.version>4.30.2</protobuf.version>
</properties>

<dependencies>
    <dependency>
        <groupId>com.google.protobuf</groupId>
        <artifactId>protobuf-java</artifactId>
        <version>${protobuf.version}</version>
    </dependency>
</dependencies>

<build>
    <extensions>
        <extension>
            <groupId>kr.motd.maven</groupId>
            <artifactId>os-maven-plugin</artifactId>
            <version>1.7.1</version>
        </extension>
    </extensions>

    <plugins>
        <plugin>
            <groupId>org.xolstice.maven.plugins</groupId>
            <artifactId>protobuf-maven-plugin</artifactId>
            <version>0.6.1</version>
            <configuration>
                <protocArtifact>
                    com.google.protobuf:protoc:${protobuf.version}:exe:${os.detected.classifier}
                </protocArtifact>
            </configuration>
            <executions>
                <execution>
                    <goals>
                        <goal>compile</goal>
                        <goal>test-compile</goal>
                    </goals>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>
```

Run:

```bash
mvn clean test
```

Generated source code is created during the build. Do not manually edit generated classes.

## 2.10 Mapping implementation

```java
@Component
public final class LogEventProtoMapper {

    public LogEventProto toProto(LogEvent event) {
        return LogEventProto.newBuilder()
                .setEventId(event.eventId().toString())
                .setOccurredAt(toTimestamp(event.occurredAt()))
                .setLevel(toProtoLevel(event.level()))
                .setService(event.service())
                .setEventType(event.eventType())
                .setMessage(event.message())
                .setTraceId(event.traceId() == null ? "" : event.traceId())
                .putAllAttributes(event.attributes())
                .build();
    }

    public LogEvent fromProto(LogEventProto proto) {
        return new LogEvent(
                UUID.fromString(proto.getEventId()),
                Instant.ofEpochSecond(
                        proto.getOccurredAt().getSeconds(),
                        proto.getOccurredAt().getNanos()),
                fromProtoLevel(proto.getLevel()),
                proto.getService(),
                proto.getEventType(),
                proto.getMessage(),
                proto.getTraceId().isBlank() ? null : proto.getTraceId(),
                Map.copyOf(proto.getAttributesMap())
        );
    }

    private Timestamp toTimestamp(Instant instant) {
        return Timestamp.newBuilder()
                .setSeconds(instant.getEpochSecond())
                .setNanos(instant.getNano())
                .build();
    }

    private LogLevelProto toProtoLevel(LogLevel level) {
        return switch (level) {
            case TRACE -> LogLevelProto.TRACE;
            case DEBUG -> LogLevelProto.DEBUG;
            case INFO -> LogLevelProto.INFO;
            case WARN -> LogLevelProto.WARN;
            case ERROR -> LogLevelProto.ERROR;
            case FATAL -> LogLevelProto.FATAL;
        };
    }

    private LogLevel fromProtoLevel(LogLevelProto level) {
        return switch (level) {
            case TRACE -> LogLevel.TRACE;
            case DEBUG -> LogLevel.DEBUG;
            case INFO -> LogLevel.INFO;
            case WARN -> LogLevel.WARN;
            case ERROR -> LogLevel.ERROR;
            case FATAL -> LogLevel.FATAL;
            case LOG_LEVEL_UNSPECIFIED, UNRECOGNIZED ->
                    throw new InvalidLogEventException("Unsupported log level: " + level);
        };
    }
}
```

The mapper is explicit on purpose. Reflection-based automatic mapping can hide incompatible defaults, enum changes, and timestamp conversion errors.

## 2.11 Codec implementation

```java
@Component
public final class ProtobufLogCodec {

    private final LogEventProtoMapper mapper;
    private final int maxPayloadBytes;

    public ProtobufLogCodec(
            LogEventProtoMapper mapper,
            @Value("${logging.protobuf.max-payload-bytes:1048576}") int maxPayloadBytes) {
        this.mapper = mapper;
        this.maxPayloadBytes = maxPayloadBytes;
    }

    public byte[] encode(LogEvent event) {
        byte[] payload = mapper.toProto(event).toByteArray();
        if (payload.length > maxPayloadBytes) {
            throw new PayloadTooLargeException(payload.length, maxPayloadBytes);
        }
        return payload;
    }

    public LogEvent decode(byte[] payload) {
        if (payload.length == 0 || payload.length > maxPayloadBytes) {
            throw new InvalidPayloadException("Invalid payload size: " + payload.length);
        }

        try {
            LogEventProto proto = LogEventProto.parseFrom(payload);
            return mapper.fromProto(proto);
        } catch (InvalidProtocolBufferException | IllegalArgumentException ex) {
            throw new InvalidPayloadException("Malformed Protobuf log event", ex);
        }
    }
}
```

Generated Protobuf messages and parsers are immutable and safe to share. Builders are mutable and should remain local to one thread or operation.

## 2.12 Framing over TCP

TCP is a byte stream. One `read()` does not equal one application message.

A receiver needs framing. A common frame is:

```text
4-byte payload length | payload bytes
```

Java 21 example:

```java
public void writeFrame(OutputStream output, byte[] payload) throws IOException {
    DataOutputStream data = new DataOutputStream(output);
    data.writeInt(payload.length);
    data.write(payload);
    data.flush();
}

public byte[] readFrame(InputStream input, int maxFrameSize) throws IOException {
    DataInputStream data = new DataInputStream(input);
    int size = data.readInt();

    if (size <= 0 || size > maxFrameSize) {
        throw new InvalidFrameException("Invalid frame size: " + size);
    }

    return data.readNBytes(size);
}
```

Never allocate a buffer from an unvalidated client-provided length. Validate the size first to prevent memory exhaustion.

Protobuf also supports delimited messages, but the application must still enforce maximum sizes and clear connection-level behavior.

## 2.13 Spring Boot HTTP endpoint

For an HTTP demonstration, use Protobuf media types:

```java
@RestController
@RequestMapping("/api/v1/logs")
public final class ProtobufLogController {

    private final ProtobufIngestionService ingestionService;

    public ProtobufLogController(ProtobufIngestionService ingestionService) {
        this.ingestionService = ingestionService;
    }

    @PostMapping(
            path = "/protobuf",
            consumes = "application/x-protobuf",
            produces = "application/json")
    public ResponseEntity<IngestionResponse> ingest(@RequestBody byte[] payload) {
        IngestionResult result = ingestionService.ingest(payload);
        return ResponseEntity.accepted().body(IngestionResponse.from(result));
    }
}
```

For production systems, prefer a dedicated `HttpMessageConverter`, gRPC, broker serializer, or framed TCP adapter instead of allowing every controller to manipulate raw bytes.

## 2.14 End-to-end data flow

1. The producer creates a canonical `LogEvent` and assigns `eventId`.
2. Business validation runs before serialization.
3. The mapper creates an immutable generated Protobuf message.
4. The encoder produces binary bytes.
5. The batcher groups multiple encoded events or creates a `LogBatchProto`.
6. Compression may run on the batch.
7. TLS protects the bytes in transit.
8. The receiver validates the frame length and transport metadata.
9. The Protobuf parser reconstructs the generated message.
10. The mapper creates the canonical domain model.
11. Semantic validation verifies identifiers, timestamps, service names, and attributes.
12. The idempotency boundary checks the event or batch identifier.
13. The repository commits accepted data.
14. The application sends an acknowledgement only after the chosen durability boundary.

Serialization success is not delivery success.

## 2.15 Validation boundaries

Protobuf validates binary structure and field types. It does not automatically enforce every business rule.

Examples requiring semantic validation:

- `event_id` must be a valid UUID.
- `service` must not be blank.
- `occurred_at` must not be unreasonably far in the future.
- `event_type` must follow the organization’s naming convention.
- attribute count and total size must be bounded.
- `LOG_LEVEL_UNSPECIFIED` must not enter storage.

```java
@Component
public final class LogEventValidator {

    public void validate(LogEvent event) {
        if (event.service() == null || event.service().isBlank()) {
            throw new InvalidLogEventException("service is required");
        }
        if (event.occurredAt().isAfter(Instant.now().plusSeconds(300))) {
            throw new InvalidLogEventException("occurredAt is too far in the future");
        }
        if (event.attributes().size() > 100) {
            throw new InvalidLogEventException("too many attributes");
        }
    }
}
```

## 2.16 Concurrency and consistency

### Codec concurrency

Generated message instances are immutable. Static parser objects can be reused. Per-call builders should not be shared.

### Batch concurrency

If multiple threads append events to a batch, use a bounded queue and a single batch-owner worker, or synchronize snapshot-and-clear operations carefully.

The safest model is often:

```text
many producers -> bounded queue -> one batch assembler -> sender workers
```

This avoids two flushes claiming the same event.

### Ordering

Protobuf does not create ordering guarantees. Ordering belongs to the transport, partitioning strategy, and consumer model.

If logs must remain ordered per source, partition by a stable key such as `sourceId` and process each partition sequentially.

### Consistency

Do not acknowledge a batch merely because Protobuf decoding succeeded. Define the actual consistency boundary:

- accepted into a durable broker
- committed to a write-ahead log
- written to primary storage
- replicated to a quorum

The ACK contract must state which boundary is guaranteed.

## 2.17 Acknowledgement and idempotency boundaries

A recommended ingestion sequence is:

```text
frame received
-> binary decoded
-> semantic validation passed
-> idempotency reservation acquired
-> durable transaction committed
-> reservation marked complete
-> ACK returned
```

A useful idempotency key is `tenantId + eventId`, or `producerId + batchId` for batch-level processing.

The receiver may see duplicates when:

- the event committed but the ACK was lost
- the connection broke after storage
- the producer timed out too aggressively
- a broker redelivered the message

Exactly-once transport is usually unrealistic. A practical design uses at-least-once delivery with idempotent durable effects.

Example table:

```sql
create table processed_event (
    tenant_id varchar(100) not null,
    event_id uuid not null,
    processed_at timestamptz not null,
    primary key (tenant_id, event_id)
);
```

Insert the idempotency record and log data in the same database transaction when they share the same database.

## 2.18 Retries and recovery

### Retryable failures

- transient network error
- broker timeout
- temporary database unavailability
- receiver overload response
- connection reset before a definitive ACK

### Non-retryable failures

- malformed Protobuf bytes
- invalid UUID
- unsupported message type
- payload above maximum size
- forbidden tenant or producer
- semantic validation failure

Use exponential backoff with jitter:

```text
nextDelay = min(maxDelay, baseDelay * 2^attempt) + randomJitter
```

Retries must reuse the same event and batch identifiers. Generating a new ID on every attempt defeats idempotency.

Persist pending batches locally or in a durable queue when producer restart must not lose unacknowledged data.

Route permanently invalid messages to a quarantine or dead-letter path with safe metadata, not unrestricted raw payload logging.

## 2.19 Scaling and backpressure

Binary serialization can reduce CPU and bandwidth, but it does not eliminate downstream capacity limits.

Use bounded queues between stages:

```text
network readers
-> decode queue
-> validation workers
-> persistence queue
-> storage writers
```

Each queue should expose:

- capacity
- current depth
- oldest item age
- rejected item count
- enqueue wait time

Backpressure options:

1. Stop reading temporarily from the connection.
2. Return HTTP `429` or `503` with retry guidance.
3. Pause broker consumption.
4. Reduce producer rate.
5. Spill to a bounded durable buffer.
6. Reject low-priority logs under a documented policy.

Virtual threads in Java 21 can simplify connection-per-task code, but they do not make CPU-intensive decoding or database capacity unlimited.

```java
@Bean(destroyMethod = "close")
ExecutorService connectionExecutor() {
    return Executors.newVirtualThreadPerTaskExecutor();
}
```

Use virtual threads for blocking I/O orchestration. Use bounded concurrency controls around databases, compression, and other finite resources.

## 2.20 Performance benchmarking

Compare JSON and Protobuf using the same logical dataset.

Measure:

- uncompressed payload bytes
- compressed payload bytes
- encode latency
- decode latency
- allocation rate
- GC pause time
- CPU utilization
- events per second
- p50, p95, and p99 end-to-end latency

Avoid benchmarking a single tiny object in a way that the JVM can optimize away. Use JMH for codec microbenchmarks and an integration load test for the full pipeline.

JMH outline:

```java
@State(Scope.Benchmark)
public class SerializationBenchmark {

    private LogEvent event;
    private ProtobufLogCodec protobuf;
    private ObjectMapper json;

    @Setup
    public void setup() {
        // create representative event and codecs
    }

    @Benchmark
    public byte[] encodeProtobuf() {
        return protobuf.encode(event);
    }

    @Benchmark
    public byte[] encodeJson() throws Exception {
        return json.writeValueAsBytes(event);
    }
}
```

A valid report should state dataset shape, JVM flags, warm-up, iterations, message size distribution, machine resources, concurrency, and whether compression was enabled.

## 2.21 Observability

Micrometer metrics:

```java
@Component
public final class InstrumentedProtobufCodec {

    private final ProtobufLogCodec delegate;
    private final Timer encodeTimer;
    private final Timer decodeTimer;
    private final DistributionSummary payloadSize;
    private final Counter decodeFailures;

    public InstrumentedProtobufCodec(ProtobufLogCodec delegate, MeterRegistry registry) {
        this.delegate = delegate;
        this.encodeTimer = registry.timer("log.protobuf.encode.duration");
        this.decodeTimer = registry.timer("log.protobuf.decode.duration");
        this.payloadSize = registry.summary("log.protobuf.payload.bytes");
        this.decodeFailures = registry.counter("log.protobuf.decode.failures");
    }

    public byte[] encode(LogEvent event) {
        return encodeTimer.record(() -> {
            byte[] bytes = delegate.encode(event);
            payloadSize.record(bytes.length);
            return bytes;
        });
    }

    public LogEvent decode(byte[] payload) {
        try {
            return decodeTimer.record(() -> delegate.decode(payload));
        } catch (RuntimeException ex) {
            decodeFailures.increment();
            throw ex;
        }
    }
}
```

Operational metrics:

- `log.protobuf.encode.duration`
- `log.protobuf.decode.duration`
- `log.protobuf.payload.bytes`
- `log.protobuf.decode.failures`
- `log.protobuf.unknown_fields`
- `log.ingestion.duplicates`
- `log.ingestion.rejected`
- `log.ingestion.queue.depth`
- `log.ingestion.ack.duration`

Logs should include correlation IDs, producer ID, batch ID, schema family, and error category. Do not log complete sensitive payloads by default.

## 2.22 Security

Protobuf is an encoding format, not encryption or authentication.

Continue using TLS or mTLS from Day 13.

Security controls:

- authenticate producer identity
- authorize tenant and source
- cap frame and message sizes
- cap repeated-field and map entry counts
- enforce decompressed-size limits
- validate timestamps and identifiers
- reject unsupported message types
- rate-limit abusive clients
- protect schema repositories and generated artifacts
- avoid writing secrets or personal data to diagnostic logs

A compact binary payload can still contain malicious or sensitive data. Binary encoding must never be treated as secrecy.

## 2.23 Schema evolution

### Safe changes

Usually compatible:

- adding a new field with a new field number
- adding a new message type
- adding an enum value when consumers handle unknown values safely
- removing a field while reserving its number and name

### Dangerous changes

- reusing a field number
- changing a field’s meaning
- changing an incompatible type
- moving a field into an incompatible union structure
- treating a previously optional concept as mandatory without migration

Example version 2:

```proto
message LogEventProto {
  string event_id = 1;
  google.protobuf.Timestamp occurred_at = 2;
  LogLevelProto level = 3;
  string service = 4;
  string event_type = 5;
  string message = 6;
  string trace_id = 7;
  map<string, string> attributes = 8;
  string environment = 9; // new compatible field
}
```

An older consumer ignores field 9. A newer consumer reading an older event receives the default empty value and must apply an explicit business default.

Compatibility tests must run in CI using previous schema fixtures.

## 2.24 Trade-offs

### Protocol Buffers advantages

- compact binary representation
- fast generated parsers
- strongly typed contracts
- cross-language code generation
- good backward and forward compatibility when field rules are respected
- useful for high-throughput internal service communication

### Protocol Buffers disadvantages

- payloads are not naturally human-readable
- code generation adds build complexity
- debugging requires schema-aware tools
- careless field-number changes can permanently break compatibility
- dynamic ad hoc fields fit less naturally than in JSON
- schema ownership and release discipline are required

### JSON versus Protobuf

Choose JSON when:

- human readability is important
- external consumers need broad compatibility
- traffic volume is moderate
- schemas change informally
- browser and HTTP tooling dominate

Choose Protobuf when:

- throughput and bandwidth matter
- contracts are centrally governed
- multiple programming languages participate
- generated types are desirable
- consumers can deploy schema-aware tooling

Many systems support both: JSON at external APIs and Protobuf for internal transport.

## 2.25 Practical example

Consider 10,000 log events per second.

Assume measured averages:

```text
JSON:      620 bytes/event
Protobuf:  210 bytes/event
```

Raw traffic:

```text
JSON:      6.2 MB/s
Protobuf:  2.1 MB/s
```

Daily raw volume:

```text
JSON:      about 536 GB/day
Protobuf:  about 181 GB/day
```

This is only an illustrative calculation. Real measurements must include headers, batching, compression, broker replication, storage indexes, and the actual event distribution.

## 2.26 Exercises

### Exercise 1 — Basic codec

Define `LogEventProto`, generate Java classes, and implement round-trip mapping.

Acceptance criteria:

- all canonical fields survive encode/decode
- invalid UUIDs are rejected
- unspecified levels are rejected
- attributes are immutable after mapping

### Exercise 2 — Size comparison

Generate 100,000 representative events and compare JSON and Protobuf byte sizes.

Report:

- mean
- median
- p95
- maximum
- total bytes
- compression result for both formats

### Exercise 3 — Compatible evolution

Add `environment = 9`.

Verify:

- old payload -> new consumer
- new payload -> old consumer
- old payload -> old consumer
- new payload -> new consumer

### Exercise 4 — Reliable batch ingestion

Build `LogBatchProto` with batch-level ACK and event-level idempotency.

Simulate an ACK loss after commit and verify that retrying does not duplicate stored events.

### Exercise 5 — Backpressure

Limit the decode queue to 1,000 items and slow storage intentionally.

Observe queue depth, rejection behavior, producer retry rate, and memory stability.

## 2.27 Test strategy

### Unit tests

- domain-to-Protobuf mapping
- Protobuf-to-domain mapping
- timestamp precision
- enum conversion
- missing and invalid values
- maximum payload size
- malformed bytes
- unknown enum handling
- attribute limits

```java
@Test
void roundTripPreservesEvent() {
    LogEvent original = TestEvents.paymentFailure();

    byte[] encoded = codec.encode(original);
    LogEvent decoded = codec.decode(encoded);

    assertThat(decoded).isEqualTo(original);
}
```

### Compatibility tests

Store binary fixtures generated by the previous schema version.

- current code reads old fixtures
- old-version test consumer reads compatible new fixtures
- reserved field numbers remain reserved
- schema-breaking changes fail CI

### Integration tests

Use Spring Boot and Testcontainers to verify:

- HTTP or TCP Protobuf ingestion
- durable database commit
- ACK after commit
- duplicate replay
- malformed payload quarantine
- restart recovery
- TLS transport

### Performance tests

- JMH encode/decode microbenchmarks
- sustained throughput test
- burst traffic test
- large attribute maps
- mixed message sizes
- JSON versus Protobuf comparison
- compressed versus uncompressed comparison

### Chaos and recovery tests

- kill receiver after commit but before ACK
- restart producer with pending batch
- interrupt network during frame transmission
- pause database writes
- inject delayed acknowledgements
- replay duplicate batches

The expected outcome is eventual durable processing without duplicate business effects and without unbounded memory growth.

## 2.28 Connection to Day 15

Day 15 established a canonical structured event and JSON validation boundary.

Day 16 keeps the same logical model but replaces the wire representation:

```text
Day 15: LogEvent -> JSON bytes -> receiver
Day 16: LogEvent -> Protobuf bytes -> receiver
```

The business model, event identity, idempotency policy, and durable ACK boundary should not depend on the serialization format.

This separation lets the system compare JSON and Protobuf objectively or support both through separate adapters.

## 2.29 Connection to Day 17

Day 17 introduces Avro and focuses more directly on schema evolution.

Protocol Buffers embeds numeric field identities in a compiled schema and generates typed code. Avro commonly transports data with a writer schema and resolves it against a reader schema, often with a schema registry in production systems.

The next lesson should compare:

- schema ownership
- writer and reader compatibility
- generated versus generic records
- registry integration
- field defaults
- backward and forward compatibility
- operational migration between schema versions

Day 16 provides the binary serialization and compatibility foundation needed for that comparison.

---

## Completion checklist

- [ ] `.proto` contract uses stable field numbers
- [ ] generated Java classes compile under Java 21
- [ ] canonical model remains independent from Protobuf
- [ ] mapping is explicit and tested
- [ ] payload and frame sizes are bounded
- [ ] semantic validation runs after decoding
- [ ] event IDs survive retries unchanged
- [ ] ACK occurs only after the defined durability boundary
- [ ] duplicate replay produces no duplicate durable effect
- [ ] queues and resource concurrency are bounded
- [ ] Micrometer metrics expose size, latency, errors, and queue pressure
- [ ] TLS and producer authorization remain enabled
- [ ] JSON and Protobuf benchmarks use the same dataset
- [ ] compatible schema evolution is proven by automated tests
