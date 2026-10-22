package linkcache

import (
	"net/url"
	"path"
	"strings"
)

// NormalizeKey canonicalizes a URL or path into a stable cache key: the
// cleaned path, lower-cased host (if any), no trailing slash, no fragment.
func NormalizeKey(raw string) string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "/"
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "/" + strings.Trim(raw, "/")
	}
	p := path.Clean("/" + u.Path)
	if len(p) > 1 {
		p = strings.TrimSuffix(p, "/")
	}
	host := strings.ToLower(u.Host)
	if host == "" {
		return p
	}
	return host + p
}
