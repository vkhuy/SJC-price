# SJC Gold Price Vietnam

Track historical SJC gold prices in Vietnam with a daily updated dataset and an interactive web chart.

![SJC Gold Price Chart](assets/SJC%20Gold%20Price%20Chart.png)

## Live website

- GitHub Pages: https://vkhuy.github.io/SJC-price/

## Highlights

- Historical daily data from 2009-07-22 to present.
- Buy/sell price tracking (`buy_1l`, `sell_1l`) in million VND per luong.
- Interactive chart with time filters: `1M`, `3M`, `6M`, `1Y`, `3Y`, `5Y`, `ALL`.
- Unit switch between `Triệu VND/Lượng` and `VND/gram`.
- Auto-update pipeline via GitHub Actions (daily run).

## Dataset Snapshot

- Date range: `2009-07-22` to `now`.
- Main columns:
	- `timestamp` (YYYY-MM-DD)
	- `buy_1l` (million VND)
	- `sell_1l` (million VND)

Primary files:

- Source dataset: `data/gold_sjc/sjc_final.csv`
- GitHub Pages dataset: `docs/data/sjc_final.csv`

## Project Structure

```text
SJC-price/
	assets/                          # Project images
	data/gold_sjc/                   # Data collection and merge scripts
		backfill_sjc_giavang.py
		backfill_sjc_giavangonline.py
		get_sjc_price.py
		merge_dataset.py
		sjc_final.csv
	docs/                            # Static website (GitHub Pages)
		index.html
		app.js
		styles.css
		data/sjc_final.csv
	.github/workflows/
		fetch_sjc_price.yml            # Daily update automation
	requirements.txt
```

## Data Pipeline

1. Backfill from historical sources:
	 - `giavang.org`
	 - `giavangonline.com`
2. Merge both datasets and resolve differences.
3. Append/update latest SJC price using `vnstock` + `sjc.com.vn` source.
4. Sync final CSV into `docs/data/` for GitHub Pages.

## Local Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Build/refresh dataset

```bash
cd data/gold_sjc
python backfill_sjc_giavang.py
python backfill_sjc_giavangonline.py
python merge_dataset.py
python get_sjc_price.py
cd ../..
cp data/gold_sjc/sjc_final.csv docs/data/sjc_final.csv
```

### 3. Run website locally

```bash
cd docs
python -m http.server 8000
```

Open: http://localhost:8000

## Automation

- Workflow: `.github/workflows/fetch_sjc_price.yml`
- Schedule: `0 6 * * *` (06:00 UTC daily)
- Steps:
	- Fetch latest SJC price
	- Update `data/gold_sjc/sjc_final.csv`
	- Sync `docs/data/sjc_final.csv`
	- Commit and push if data changed

## Data Sources

- https://github.com/thinh-vu/vnstock
- https://sjc.com.vn/
- https://giavang.org/
- https://giavangonline.com/

## Notes

- Prices shown are SJC 1L buy/sell values.
- Displayed website data is loaded from `docs/data/sjc_final.csv`.

## Contributing

Contributions are welcome for data quality improvements, bug fixes, and UI enhancements.

### How to contribute

1. Fork this repository.
2. Create a feature branch:

```bash
git checkout -b feat/your-change
```

3. Make your changes and verify locally:

```bash
pip install -r requirements.txt
cd data/gold_sjc
python merge_dataset.py
python get_sjc_price.py
cd ../..
python -m http.server 8000 --directory docs
```

4. Commit with a clear message and push your branch.
5. Open a Pull Request to `main` with:
	 - What changed
	 - Why it changed
	 - Any data source or logic impact

### Contribution tips

- Keep changes focused and small per PR.
- If you change data scripts, update both:
	- `data/gold_sjc/sjc_final.csv`
	- `docs/data/sjc_final.csv`
- For larger changes, open an issue first to discuss approach.
