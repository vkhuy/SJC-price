import os
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime, timedelta
import time
from vnstock.explorer.misc import sjc_gold_price

SJC_API = "https://sjc.com.vn/GoldPrice/Services/PriceService.ashx"
NAME_KEYS = {"name", "title", "loai_vang", "loaivang", "gold_name", "ten", "tenloaivang"}
BUY_KEYS = {"buy", "buy_price", "giamua", "gia_mua", "mua"}
SELL_KEYS = {"sell", "sell_price", "giaban", "gia_ban", "ban"}

def _to_numeric_price(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^\d]", "", str(value))
    if not cleaned:
        return None
    return float(cleaned)

def _extract_prices_from_json(payload):
    rows = []

    def walk(node):
        if isinstance(node, dict):
            lower_keys = {str(k).lower(): k for k in node.keys()}
            name_key = next((lower_keys[k] for k in lower_keys if k in NAME_KEYS), None)
            buy_key = next((lower_keys[k] for k in lower_keys if k in BUY_KEYS), None)
            sell_key = next((lower_keys[k] for k in lower_keys if k in SELL_KEYS), None)

            if buy_key is not None and sell_key is not None:
                name = str(node.get(name_key, "")) if name_key is not None else ""
                rows.append((name, _to_numeric_price(node.get(buy_key)), _to_numeric_price(node.get(sell_key))))

            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    for name, buy_price, sell_price in rows:
        normalized_name = name.strip().lower()
        if buy_price is not None and sell_price is not None and "sjc" in normalized_name and "1l" in normalized_name:
            return buy_price, sell_price

    for _, buy_price, sell_price in rows:
        if buy_price is not None and sell_price is not None:
            return buy_price, sell_price

    return None, None

def fetch_sjc_from_sjc_api(max_retries=3, delay=5):
    """Fallback source: fetch directly from SJC API endpoint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://sjc.com.vn/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }

    for attempt in range(max_retries):
        print(f"Trying SJC API attempt {attempt + 1}/{max_retries}: {SJC_API}")
        for method in ("get", "post"):
            try:
                request_fn = requests.get if method == "get" else requests.post
                response = request_fn(SJC_API, headers=headers, timeout=20)
                if response.status_code >= 400:
                    continue

                try:
                    payload = response.json()
                    buy_price, sell_price = _extract_prices_from_json(payload)
                    if buy_price is not None and sell_price is not None:
                        print(f"Fetched API prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                        return buy_price, sell_price, datetime.now().strftime("%Y-%m-%d")
                except Exception:
                    pass

                text = response.text
                try:
                    tables = pd.read_html(StringIO(text))
                except Exception:
                    tables = []

                for table in tables:
                    if table.empty:
                        continue
                    row_text = table.astype(str).agg(" ".join, axis=1).str.lower()
                    matched_rows = table[row_text.str.contains("sjc", na=False) & row_text.str.contains("1l", na=False)]
                    if matched_rows.empty:
                        continue

                    selected_row = matched_rows.iloc[0]
                    price_values = [_to_numeric_price(v) for v in selected_row.values]
                    price_values = [v for v in price_values if v is not None]
                    if len(price_values) >= 2:
                        buy_price, sell_price = price_values[0], price_values[1]
                        print(f"Fetched API prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                        return buy_price, sell_price, datetime.now().strftime("%Y-%m-%d")

                # Match text containing "SJC ... 1L" followed by two prices with thousand separators.
                pattern = re.compile(r"(?is)sjc[^\n]{0,80}?1l.*?(\d{2,3}(?:[.,]\d{3})+).*?(\d{2,3}(?:[.,]\d{3})+)")
                match = pattern.search(text)
                if match:
                    buy_price = _to_numeric_price(match.group(1))
                    sell_price = _to_numeric_price(match.group(2))
                    if buy_price is not None and sell_price is not None:
                        print(f"Fetched API prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                        return buy_price, sell_price, datetime.now().strftime("%Y-%m-%d")
            except Exception as e:
                print(f"SJC API {method.upper()} attempt failed: {str(e)}")

        if attempt < max_retries - 1:
            print(f"Waiting {delay} seconds before retrying SJC API...")
            time.sleep(delay)

    return None, None, None

def fetch_sjc_with_retry(max_retries=3, delay=5):
    """Fetch SJC data via vnstock with retry logic."""
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}...")
            gold_data = sjc_gold_price()
            
            if gold_data is not None and len(gold_data) > 0:
                print("Successfully fetched data")
                return gold_data
            else:
                print(f"No data returned on attempt {attempt + 1}")
                
        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            
        if attempt < max_retries - 1:
            print(f"Waiting {delay} seconds before retry...")
            time.sleep(delay)
    
    return None

def fetch_sjc_from_giavang_org(max_days_back=3):
    """Fallback source: fetch SJC from giavang.org historical pages."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SJC-price-bot/1.0)"
    }

    for day_offset in range(max_days_back):
        target_date = datetime.now() - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://giavang.org/trong-nuoc/sjc/lich-su/{date_str}.html"

        try:
            print(f"Trying fallback source for {date_str}: {url}")
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table")
            if table is None:
                continue

            df = pd.read_html(StringIO(str(table)))[0]

            if "Khu vực" in df.columns:
                df = df[df["Khu vực"].astype(str).str.contains("Hồ Chí Minh", case=False, na=False)]
            if "Loại vàng" in df.columns:
                df = df[df["Loại vàng"].astype(str).str.contains("1L", case=False, na=False)]

            if df.empty:
                continue

            row = df.iloc[0]
            buy_price = pd.to_numeric(str(row.get("Mua vào", "")).replace(",", ""), errors="coerce")
            sell_price = pd.to_numeric(str(row.get("Bán ra", "")).replace(",", ""), errors="coerce")

            if pd.notna(buy_price) and pd.notna(sell_price):
                print(f"Fetched fallback prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                return float(buy_price), float(sell_price), date_str
        except Exception as e:
            print(f"Fallback fetch failed for {date_str}: {str(e)}")

    return None, None, None

def fetch_sjc_from_giavangonline(max_days_back=3):
    """Fallback source: fetch SJC from giavangonline.com."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SJC-price-bot/1.0)"
    }

    for day_offset in range(max_days_back):
        target_date = datetime.now() - timedelta(days=day_offset)
        date_str = target_date.strftime("%Y-%m-%d")
        url = f"https://giavangonline.com/mobile/goldhistory.php?date={target_date.strftime('%Y/%m/%d')}"

        try:
            print(f"Trying fallback source for {date_str}: {url}")
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="home")
            if table is None:
                continue

            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) >= 2 and "sjc 1l" in cols[0].get_text().strip().lower():
                    price_text = cols[1].get_text().strip()
                    if " / " not in price_text:
                        continue
                    buy_str, sell_str = price_text.split(" / ", 1)
                    buy_price = pd.to_numeric(buy_str.replace(",", ""), errors="coerce")
                    sell_price = pd.to_numeric(sell_str.replace(",", ""), errors="coerce")
                    if pd.notna(buy_price) and pd.notna(sell_price):
                        print(f"Fetched fallback prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                        return float(buy_price), float(sell_price), date_str
        except Exception as e:
            print(f"Fallback fetch failed for {date_str}: {str(e)}")

    return None, None, None

def fetch_and_save_sjc_price():   
    csv_file = 'sjc_final.csv'
    
    try:
        buy_price = None
        sell_price = None
        record_date = datetime.now().strftime("%Y-%m-%d")

        # Fetch SJC gold price data with retry
        print("Fetching SJC price...")
        print("Source (fallback order): vnstock -> SJC API -> giavang.org -> giavangonline.com")
        gold_data = fetch_sjc_with_retry(max_retries=10, delay=10)
        
        if gold_data is not None and len(gold_data) > 0:
            sjc_row = gold_data.iloc[0]
            buy_price = sjc_row.get('buy_price')
            sell_price = sjc_row.get('sell_price')

        if buy_price is None or sell_price is None:
            print("vnstock source unavailable, trying SJC API fallback...")
            buy_price, sell_price, fallback_date = fetch_sjc_from_sjc_api(max_retries=3, delay=5)
            if buy_price is not None and sell_price is not None and fallback_date is not None:
                record_date = fallback_date

        if buy_price is None or sell_price is None:
            print("SJC API source unavailable, trying fallback source giavang.org...")
            buy_price, sell_price, fallback_date = fetch_sjc_from_giavang_org(max_days_back=3)
            if buy_price is not None and sell_price is not None and fallback_date is not None:
                record_date = fallback_date

        if buy_price is None or sell_price is None:
            print("giavang.org source unavailable, trying fallback source giavangonline.com...")
            buy_price, sell_price, fallback_date = fetch_sjc_from_giavangonline(max_days_back=3)
            if buy_price is not None and sell_price is not None and fallback_date is not None:
                record_date = fallback_date

        if buy_price is None or sell_price is None:
            print("Failed to fetch SJC price from all sources")
            return False

        print(f"Fetched prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")

        new_record = {
            'timestamp': record_date,
            'buy_1l': round(buy_price / 1_000_000, 2),  # Convert from VND to million VND
            'sell_1l': round(sell_price / 1_000_000, 2)
        }

        # Read the current CSV file or create a new one
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            print(f"Reading current file with {len(df)} records")
            
            # Check if record date already exists (avoid duplicates)
            if new_record['timestamp'] in df['timestamp'].values:
                print(f"Record for {new_record['timestamp']} already exists. Updating...")
                df.loc[df['timestamp'] == new_record['timestamp'], ['buy_1l', 'sell_1l']] = [new_record['buy_1l'], new_record['sell_1l']]
            else:
                df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        else:
            df = pd.DataFrame([new_record])
            print("Creating new CSV file")
        
        df.to_csv(csv_file, index=False)
        print(f"Saved SJC gold price: Buy {new_record['buy_1l']} - Sell {new_record['sell_1l']} million VND")
        print(f"Total records: {len(df)}")

        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("SJC Gold Price Fetcher")
    print("=" * 50)
    success = fetch_and_save_sjc_price()
    exit(0 if success else 1)
