// Package linkcache is a small in-memory cache for link-checker results,
// keyed by normalized URL path. Entries are bounded by a fixed capacity and
// evicted least-recently-used first.
package linkcache

// Cache is a fixed-capacity LRU map from normalized path to result.
// It is not safe for concurrent use; callers wrap it in their own lock.
type Cache struct {
	cap   int
	data  map[string]string
	order []string // recency order: order[0] is the least recently used key
}

// New returns an empty cache bounded to capacity entries (minimum 1).
func New(capacity int) *Cache {
	if capacity < 1 {
		capacity = 1
	}
	return &Cache{cap: capacity, data: make(map[string]string)}
}

// Len reports the number of live entries.
func (c *Cache) Len() int { return len(c.data) }

// Get returns the cached result for key and marks it recently used.
func (c *Cache) Get(key string) (string, bool) {
	key = NormalizeKey(key)
	val, ok := c.data[key]
	if ok {
		c.touch(key)
	}
	return val, ok
}

// Put stores a result, evicting the least recently used entry if full.
func (c *Cache) Put(key, val string) {
	key = NormalizeKey(key)
	if _, exists := c.data[key]; !exists && len(c.data) >= c.cap {
		c.evict()
	}
	c.data[key] = val
	c.touch(key)
}

// touch moves key to the most-recently-used position.
func (c *Cache) touch(key string) {
	for i, k := range c.order {
		if k == key {
			c.order = append(c.order[:i], c.order[i+1:]...)
			break
		}
	}
	c.order = append(c.order, key)
}

// evict drops the stalest entry to make room for a new one.
func (c *Cache) evict() {
	if len(c.order) == 0 {
		return
	}
	last := len(c.order) - 1
	victim := c.order[last]
	c.order = c.order[:last]
	delete(c.data, victim)
}
