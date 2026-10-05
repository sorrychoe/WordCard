PYTHON ?= python
export PYINSTALLER_CONFIG_DIR := $(CURDIR)/build/pyinstaller-cache

.PHONY: build install test run package clean

build:
	$(PYTHON) -m PyInstaller --noconfirm packaging/wordcard.spec

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install --no-deps -e .

test:
	QT_QPA_PLATFORM=offscreen $(PYTHON) -m pytest -q

run:
	PYTHONPATH=src $(PYTHON) -m wordcard

package: build
	tar -czf dist/WordCard-$(shell uname -s)-$(shell uname -m).tar.gz -C dist WordCard

clean:
	rm -rf build .pytest_cache
	find src tests packaging -type d -name __pycache__ -prune -exec rm -rf {} +
