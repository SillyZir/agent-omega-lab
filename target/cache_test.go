package linkcache

import "testing"

// These are the tests that existed when the bug was reported. They pass on
// the buggy code: none of them checks WHICH entry an eviction removes.

func TestPutGetRoundtrip(t *testing.T) {
	c := New(4)
	c.Put("/docs/a", "ok")
	if v, ok := c.Get("/docs/a"); !ok || v != "ok" {
		t.Fatalf("Get(/docs/a) = %q, %v; want ok, true", v, ok)
	}
}

func TestCapacityBound(t *testing.T) {
	c := New(2)
	c.Put("/a", "1")
	c.Put("/b", "2")
	c.Put("/c", "3")
	if c.Len() > 2 {
		t.Fatalf("Len() = %d after inserting 3 into cap-2 cache; want <= 2", c.Len())
	}
}

func TestOverwriteDoesNotGrow(t *testing.T) {
	c := New(2)
	c.Put("/a", "1")
	c.Put("/a", "2")
	if c.Len() != 1 {
		t.Fatalf("Len() = %d after overwriting one key; want 1", c.Len())
	}
	if v, _ := c.Get("/a"); v != "2" {
		t.Fatalf("Get(/a) = %q; want 2", v)
	}
}
