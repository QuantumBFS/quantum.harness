LATEXMK ?= latexmk
MAIN := main
BUILD_DIR := build
BUILD_PDF := $(BUILD_DIR)/$(MAIN).pdf
TEX_SOURCES := $(wildcard sections/*.tex appendices/*.tex figures/*.tex)

.PHONY: all clean check dist render

all: $(BUILD_PDF)

$(BUILD_PDF): $(MAIN).tex references.bib $(TEX_SOURCES)
	mkdir -p $(BUILD_DIR)
	$(LATEXMK) -xelatex -outdir=$(BUILD_DIR) -interaction=nonstopmode -halt-on-error $(MAIN).tex

check: $(BUILD_PDF)
	@test -f $(BUILD_DIR)/$(MAIN).log
	@! grep -E "undefined references|Citation .* undefined|There were undefined|Overfull \\\\hbox|Overfull \\\\vbox" $(BUILD_DIR)/$(MAIN).log
	@pdfinfo $(BUILD_PDF) | grep -E "^(Pages|Page size|File size):"

dist: $(BUILD_PDF)
	cp $(BUILD_PDF) $(MAIN).pdf

render: $(BUILD_PDF)
	mkdir -p .rendered
	pdftoppm -png -r 144 $(BUILD_PDF) .rendered/page

clean:
	rm -rf $(BUILD_DIR) .rendered
