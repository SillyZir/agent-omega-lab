# [Bug]: Hit rate collapses under load — cache evicts its hottest entry at capacity

**Labels:** bug

Once the cache reaches capacity, frequently-read entries vanish immediately
while stale ones survive. In a crawl over ~2k links with a 512-entry cache we
measured a 4% hit rate; the same workload against a plain map bounded by hand
gets ~70%.

## Steps to reproduce

```go
c := linkcache.New(2)
c.Put("/hot", "H")
c.Put("/cold", "C")
c.Get("/hot")        // /hot is now the most recently used entry
c.Put("/new", "N")   // cache is full — this must evict /cold
if _, ok := c.Get("/hot"); !ok {
    panic("the hottest entry was evicted")
}
```

The panic fires every time. `/cold` — untouched since insertion — is still
present afterwards.

## Expected

Eviction removes the least-recently-used entry (`/cold` above), as the package
documentation states.

## Actual

The most-recently-used entry (`/hot`) is removed. Whatever was read last is
always the first thing to die when the cache is full.
