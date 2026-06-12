# fwi-water-quality

Data analysis for the Fish Welfare Initiative (FWI): A controlled effectiveness study assessing whether providing farmers with water quality readings and corrective actions improves pond water quality at farms in Eluru, Andhra Pradesh, India.

The full write-up is [`outputs/results.md`](outputs/results.md), with a panel-by-panel figure guide in [`outputs/figures.md`](outputs/figures.md).

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python main.py       # primary analysis
.venv/bin/python main_sia.py   # post-hoc SIA analysis
```

`main.py` runs the primary (blind) analysis — baseline balance, the Day-3 OOR resolution rates with Fisher's exact test, the per-parameter improvement tests, and the Day-2 vs Day-3 comparison — and regenerates Fig1–Fig9 in `outputs/plots/`. `main_sia.py` is the post-hoc analysis of farmers' self-initiated actions on the unblinded workbook (results.md §6).

## Layout

```
inputs/            study protocol (PDF) and datasets
  data/            cleaned Phase 2 workbooks (anonymized and unblinded)
src/               analysis, SIA, and plotting modules
main.py            primary analysis pipeline
main_sia.py        post-hoc SIA pipeline
outputs/           everything generated
  results.md       results write-up (start here)
  figures.md       figure walkthrough
  plots/           Fig1–Fig9
```
