checkfiles = asyncmy/ tests/ examples/ scripts/ conftest.py build_cython.py
py_warn = PYTHONDEVMODE=1
MYSQL_PASS ?= "123456"

up:
	@uv lock --upgrade
	$(MAKE) deps options=--frozen

deps:
	uv sync --all-groups $(options)

_style:
	@ruff format $(checkfiles)
	@ruff check --fix $(checkfiles)

style: deps _style

_stubtest:
	@stubtest asyncmy --mypy-config-file pyproject.toml --allowlist stubtest_allowlist.txt \
		--ignore-missing-stub --ignore-disjoint-bases --ignore-positional-only

_check:
	@ruff format --check $(checkfiles) || (echo "Please run 'make style' to auto-fix style issues" && false)
	@ruff check $(checkfiles)
	@mypy $(checkfiles)
	$(MAKE) _stubtest

stubs: deps
	@python scripts/gen_stubs.py
	$(MAKE) _stubtest

check: deps _check

_test:
	$(py_warn) MYSQL_PASS=$(MYSQL_PASS) pytest

test: deps _test

clean:
	@rm -rf *.so && rm -rf build && rm -rf dist && rm -rf asyncmy/*.c && rm -rf asyncmy/*.so && rm -rf asyncmy/*.html

build: clean
	@uv build

benchmark: deps
	@python -m benchmark.run_all

ci: deps _check _test
