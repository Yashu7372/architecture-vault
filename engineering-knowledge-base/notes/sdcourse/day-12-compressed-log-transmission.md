# Day 12 — Compressed Log Transmission

## 1. Public source material

Publicly visible curriculum item:

- **Day 12:** Add compression to reduce network bandwidth usage.
- **Visible output:** Compressed log transmission with measurable bandwidth reduction.

Source: [Hands-On Distributed Systems curriculum](https://sdcourse.substack.com/p/hands-on-distributed-systems-with).

The remainder is an original standalone lesson.

---

## 2. Original lesson

## Why this matters

Logs contain repeated field names, timestamps, service names, and common message patterns, so they often compress well. Compression lowers bandwidth and can increase effective throughput, but it consumes CPU and introduces decompression safety risks.

## First principles

Compression exchanges CPU time for fewer bytes. The correct measure is not compression ratio alone, but total system cost: producer CPU, collector CPU, network bytes, latency, and throughput.

## Terminology

- **Compression ratio:** Uncompressed bytes divided by compressed bytes.
- **Codec:** Compression algorithm and format.
- **Compression level:** CPU-versus-size tuning parameter.
- **Compression bomb:** Small encoded input expanding into excessive output.
- **Content encoding:** Protocol metadata identifying the codec.

## Requirements

- codec negotiation or explicit versioning
- compression applied after batching
- uncompressed and compressed size limits
- checksum or framing validation
- measurable ratio and CPU cost
- fallback for small payloads
- safe decompression

## Architecture

```mermaid
flowchart LR
    E[Events] --> B[Batch Builder]
    B --> S[Serializer]
    S --> C[Compressor]
    C --> F[Network Frame]
    F --> D[Decompressor]
    D --> V[Validator]
    V --> P[Parser and Storage]
```

## Wire contract

```java
public record CompressedBatchFrame(
        byte protocolVersion,
        CompressionCodec codec,
        int uncompressedLength,
        int compressedLength,
        long checksum,
        byte[] payload) {}

public enum CompressionCodec { NONE, GZIP }
```

The receiver must validate lengths before allocating buffers.

## Java 21/Spring Boot guidance

GZIP is available in the JDK and is suitable for the first implementation:

```java
static byte[] gzip(byte[] input) throws IOException {
    ByteArrayOutputStream target = new ByteArrayOutputStream();
    try (GZIPOutputStream gzip = new GZIPOutputStream(target)) {
        gzip.write(input);
    }
    return target.toByteArray();
}
```

Decompress with a hard maximum output size rather than calling an unbounded convenience method.

```java
static byte[] gunzip(byte[] input, int maxOutputBytes) throws IOException {
    try (var gzip = new GZIPInputStream(new ByteArrayInputStream(input));
         var output = new ByteArrayOutputStream()) {
        byte[] buffer = new byte[8192];
        int total = 0;
        for (int read; (read = gzip.read(buffer)) >= 0;) {
            total += read;
            if (total > maxOutputBytes) throw new IOException("decompressed payload too large");
            output.write(buffer, 0, read);
        }
        return output.toByteArray();
    }
}
```

## Component responsibilities

- **Serializer:** Produces canonical batch bytes.
- **Compression policy:** Decides whether compression is beneficial.
- **Compressor:** Encodes with a named codec.
- **Frame encoder:** Records codec, lengths, and integrity metadata.
- **Decompressor:** Enforces expansion limits.
- **Validator:** Confirms decoded length and checksum.

## End-to-end flow

1. Build a batch.
2. Serialize it to bytes.
3. Skip compression below a configurable threshold.
4. Compress and compare encoded size.
5. Build the framed payload.
6. Send it over TCP or UDP where size permits.
7. Receiver validates metadata.
8. Receiver safely decompresses.
9. Receiver verifies checksum and processes the original batch.

## Concurrency and consistency

Compression is CPU-bound. Use a bounded executor sized from available processors rather than unlimited tasks. Preserve batch order by associating completion with sequence numbers if compression runs in parallel.

## Acknowledgement and idempotency boundaries

Compression does not change the logical identity of a batch. Retries must retain the same batch and event IDs even if recompression produces different bytes. Acknowledgement remains tied to durable processing of the decoded logical batch, not receipt of compressed bytes.

## Retries and recovery

Retry transport failures using the original logical batch. Codec errors caused by corrupt data are non-retryable unless the frame is retransmitted from a verified source copy. Store codec and protocol version with pending batches.

## Scaling and backpressure

Bound queued compression tasks and total pending uncompressed bytes. When CPU is saturated, either reduce compression level, bypass compression temporarily, or apply upstream backpressure. Adaptive decisions must be visible through metrics.

## Observability

Track uncompressed bytes, compressed bytes, ratio, compression/decompression latency, codec failures, skipped-small batches, CPU utilization, expansion-limit rejections, and effective network throughput.

## Security

Enforce compressed and decompressed size limits, reject unknown codecs, validate checksums, avoid trusting declared lengths, and authenticate/encrypt the transport in Day 13. Compression before encryption is effective; compression of attacker-controlled data mixed with secrets can create side channels, so never combine secrets into log payloads.

## Trade-offs

GZIP is ubiquitous but may use more CPU than modern alternatives. Faster codecs can improve throughput but add dependencies and compatibility concerns. Compressing tiny payloads may increase size, which is why compression should follow batching and use a minimum threshold.

## Exercises

1. Add `NONE` and `GZIP` codecs.
2. Measure ratio at several batch sizes.
3. Add a minimum compression threshold.
4. Reject excessive expansion.
5. Compare end-to-end throughput with and without compression.

## Test strategy

Test round trips, empty and tiny payloads, corrupted frames, incorrect lengths, unknown codecs, maximum expansion, concurrent compression, retry identity preservation, and measurable bandwidth reduction.

## Lesson connections

Day 11 creates efficient batches. Day 12 compresses them. Day 13 protects the compressed transport using TLS.