# Streaming Responses

Gakido supports streaming responses to handle large downloads without loading the entire body into memory. This is essential for downloading large files, processing real-time data feeds, or handling chunked transfer encoding efficiently.

## Basic Usage

### Synchronous Streaming

```python
from gakido import Client

client = Client()

# Stream a large file
with client.stream("GET", "https://example.com/large-file.zip") as response:
    print(f"Status: {response.status_code}")
    
    # Iterate over chunks
    for chunk in response.iter_bytes(chunk_size=8192):
        # Process each chunk (e.g., write to file, compute hash)
        process(chunk)
```

### Asynchronous Streaming

```python
import asyncio
from gakido import AsyncClient

async def download():
    client = AsyncClient()
    
    async with await client.stream("GET", "https://example.com/large-file.zip") as response:
        async for chunk in response.aiter_bytes(chunk_size=8192):
            process(chunk)

asyncio.run(download())
```

## StreamingResponse API

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `reason` | `str` | HTTP reason phrase |
| `http_version` | `str` | HTTP version (e.g., "1.1") |
| `headers` | `dict[str, str]` | Response headers (case-insensitive keys) |
| `raw_headers` | `list[tuple[str, str]]` | Headers in original order |

### Methods

#### `iter_bytes(chunk_size=8192)`

Iterate over the response body in chunks.

```python
with client.stream("GET", url) as response:
    for chunk in response.iter_bytes(chunk_size=16384):
        file.write(chunk)
```

#### `iter_lines(chunk_size=8192, decode="utf-8")`

Iterate over the response body line by line.

```python
with client.stream("GET", url) as response:
    for line in response.iter_lines():
        print(line)  # Already decoded to str
```

#### `read()`

Read the entire response body into memory. Use with caution for large responses.

```python
with client.stream("GET", url) as response:
    body = response.read()  # Returns bytes
```

#### `close()`

Close the response and release resources. Called automatically when using context manager.

## AsyncStreamingResponse API

The async version has the same properties but uses async methods:

| Method | Description |
|--------|-------------|
| `aiter_bytes(chunk_size=8192)` | Async iterate over chunks |
| `aiter_lines(chunk_size=8192, decode="utf-8")` | Async iterate over lines |
| `read()` | Async read entire body |
| `close()` | Async close response |

## Examples

### Download to File

```python
from gakido import Client

client = Client()

with client.stream("GET", "https://example.com/video.mp4") as response:
    with open("video.mp4", "wb") as f:
        for chunk in response.iter_bytes(chunk_size=65536):
            f.write(chunk)
```

### Process JSON Lines (NDJSON)

```python
import json
from gakido import Client

client = Client()

with client.stream("GET", "https://api.example.com/events") as response:
    for line in response.iter_lines():
        if line:
            event = json.loads(line)
            handle_event(event)
```

### Progress Tracking

```python
from gakido import Client

client = Client()

with client.stream("GET", url) as response:
    content_length = int(response.headers.get("content-length", 0))
    downloaded = 0
    
    for chunk in response.iter_bytes():
        downloaded += len(chunk)
        if content_length:
            progress = (downloaded / content_length) * 100
            print(f"\rProgress: {progress:.1f}%", end="")
```

### Async Concurrent Downloads

```python
import asyncio
from gakido import AsyncClient

async def download(client, url, filename):
    async with await client.stream("GET", url) as response:
        with open(filename, "wb") as f:
            async for chunk in response.aiter_bytes():
                f.write(chunk)

async def main():
    client = AsyncClient()
    
    urls = [
        ("https://example.com/file1.zip", "file1.zip"),
        ("https://example.com/file2.zip", "file2.zip"),
        ("https://example.com/file3.zip", "file3.zip"),
    ]
    
    await asyncio.gather(*[
        download(client, url, filename) 
        for url, filename in urls
    ])

asyncio.run(main())
```

### Streaming with Decompression

Gakido automatically decompresses gzip/deflate/brotli responses when `auto_decompress=True` (default). For streaming, compressed content is accumulated and decompressed at the end of each transfer-encoding chunk or content-length block.

```python
client = Client(auto_decompress=True)  # Default

with client.stream("GET", url) as response:
    for chunk in response.iter_bytes():
        # Chunks are automatically decompressed
        process(chunk)
```

To receive raw compressed data:

```python
client = Client(auto_decompress=False)

with client.stream("GET", url) as response:
    for chunk in response.iter_bytes():
        # Raw compressed bytes
        handle_compressed(chunk)
```

## Important Notes

1. **Always close the response**: Use context managers (`with`/`async with`) to ensure resources are released.

2. **Connection not reused**: Streaming responses do not return the connection to the pool. Each stream creates a new connection.

3. **Headers available immediately**: Response headers are parsed before streaming begins, so you can check status codes and content-length before consuming the body.

4. **HTTP/2 limitation**: Streaming is currently only supported for HTTP/1.1 in the sync client. The async client supports HTTP/1.1 streaming.

5. **Memory efficiency**: For truly large files, use small chunk sizes and write directly to disk rather than accumulating in memory.
