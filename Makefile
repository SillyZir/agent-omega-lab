.PHONY: setup demo demo-live verify inject realworld web site-deploy open-prs clean
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

site-deploy:      ## build + audit + push omegademo.com (CI re-audits, then deploys)
	python3 tools/deploy_site.py "$(MSG)"

open-prs:         ## verify the open-PR snapshot against GitHub and restamp it
	python3 tools/refresh_open_prs.py

clean:
	rm -rf .work
