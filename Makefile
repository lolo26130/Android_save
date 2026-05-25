VENV    := .venv/bin
PYTHON  := $(VENV)/python
PYTEST  := $(PYTHON) -m pytest
SPHINX  := $(VENV)/sphinx-build
DOCS_SRC := docs/source
DOCS_OUT := docs/build/html

.PHONY: all test docs clean

all: test docs

test:
	$(PYTEST) tests/ -v

docs:
	$(SPHINX) -b html $(DOCS_SRC) $(DOCS_OUT) -q
	@echo "Doc disponible : $(DOCS_OUT)/index.html"

clean:
	rm -rf $(DOCS_OUT)
