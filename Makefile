.PHONY: setup demo demo-live verify inject realworld web site-build site-gate site-deploy open-prs clean
.DEFAULT_GOAL := demo

web:              ## browser console at http://127.0.0.1:8377 (local only)
	python3 tools/web.py

setup:            ## fresh working checkout of the seeded target
	python3 demo.py setup

demo:             ## the headline demo (recorded model stages + live everything else)
	python3 demo.py all

demo-live:        ## same demo with real claude sessions (needs claude CLI auth)
	python3 demo.py all --live

verify:           ## machine-checkable: differential + gate wall + all injections
	python3 demo.py verify

inject:           ## just the six blocked-failure scenarios
	python3 demo.py inject

realworld:        ## reproduce a real ground-truth issue (network + claude auth)
	python3 realworld/reproduce.py

site-build:       ## build + audit into dist/ — local only, publishes nothing
	python3 tools/deploy_site.py build

site-gate:        ## regression suite for the publication gates (publishes nothing)
	python3 tools/deploy_site.py --self-test

# This recipe used to read `python3 tools/deploy_site.py "$(MSG)"`, which with MSG unset
# passed the empty string as a commit message. That failed closed only because git happens
# to reject an empty -m; measured against the stubbed suite, the pre-fix script reached
# both commit and push on that path. It was a second unguarded entrance to the publish
# pipeline, surviving on an accident rather than a gate.
#
# The test is in the recipe, not an `ifndef` conditional: make evaluates conditionals when
# it parses the file, so an `ifndef MSG` here would abort `make demo` too.
# MSG travels to the recipe via the environment, not via $(MSG) interpolation
# into the shell line: quotes, backticks and $() in a commit message must be
# data, never shell syntax.
site-deploy: export OMEGA_MSG = $(MSG)
site-deploy:      ## build + audit + PUSH omegademo.com (CI re-audits, then deploys)
	@test -n "$$(printf '%s' "$$OMEGA_MSG" | tr -d '[:space:]')" || { \
	  echo 'make site-deploy: MSG is required, e.g. make site-deploy MSG="fix the nav"'; \
	  exit 1; }
	python3 tools/deploy_site.py publish -m "$$OMEGA_MSG"

open-prs:         ## verify the open-PR snapshot against GitHub and restamp it
	python3 tools/refresh_open_prs.py

clean:
	rm -rf .work
