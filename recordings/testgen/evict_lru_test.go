package linkcache

import "testing"

// Regression test for issue #1: at capacity, eviction must remove the
// least-recently-used entry, not the most-recently-used one.

func TestEvictRemovesLeastRecentlyUsed(t *testing.T) {
	c := New(2)
	c.Put("/hot", "H")
	c.Put("/cold", "C")
	if _, ok := c.Get("/hot"); !ok {
		t.Fatalf("Get(/hot) missing before eviction; want present")
	}
	// Cache is full; /cold is now the least recently used entry.
	c.Put("/new", "N")
	if _, ok := c.Get("/hot"); !ok {
		t.Fatalf("Get(/hot) = _, false after inserting /new; the most recently used entry was evicted, want /cold evicted instead")
	}
	if _, ok := c.Get("/cold"); ok {
		t.Fatalf("Get(/cold) = _, true after inserting /new; want the least recently used entry /cold evicted")
	}
	if v, ok := c.Get("/new"); !ok || v != "N" {
		t.Fatalf("Get(/new) = %q, %v; want N, true", v, ok)
	}
}
