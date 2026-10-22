package linkcache

import "testing"

func TestNormalizeKey(t *testing.T) {
	cases := map[string]string{
		"/docs/../a/b/":               "/a/b",
		"":                            "/",
		"https://Example.COM/x/./y#f": "example.com/x/y",
		"plain":                       "/plain",
	}
	for in, want := range cases {
		if got := NormalizeKey(in); got != want {
			t.Errorf("NormalizeKey(%q) = %q; want %q", in, got, want)
		}
	}
}
