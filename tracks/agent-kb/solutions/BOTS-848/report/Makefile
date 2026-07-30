LATEXMK ?= latexmk
MAIN := main
TEX_SOURCES := $(wildcard sections/*.tex appendices/*.tex figures/*.tex)

.PHONY: all clean check render

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex references.bib $(TEX_SOURCES)
	$(LATEXMK) -xelatex -interaction=nonstopmode -halt-on-error $(MAIN).tex

check: $(MAIN).pdf
	@! grep -E "undefined references|Citation .* undefined|There were undefined|Overfull \\\\hbox|Overfull \\\\vbox" $(MAIN).log
	@pdfinfo $(MAIN).pdf | grep -E "^(Pages|Page size|File size):"

render: $(MAIN).pdf
	mkdir -p .rendered
	pdftoppm -png -r 144 $(MAIN).pdf .rendered/page

clean:
	$(LATEXMK) -C $(MAIN).tex
	rm -rf .rendered
