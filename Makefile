.PHONY: build images check

build:        ## regenerate the managed slots in public/
	python3 build.py

images:       ## also regenerate card thumbnails and share images (Pillow, node + Playwright)
	python3 build.py --images

check:        ## verify slots, nav, links and images; non-zero exit on problems
	python3 build.py --check
