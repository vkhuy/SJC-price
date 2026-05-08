import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime, timedelta
import time
from vnstock.explorer.misc import sjc_gold_price

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
                df = df[df["Khu vực"].astype(str).str.contains("Hồ Chí Minh", na=False)]
            if "Loại vàng" in df.columns:
                df = df[df["Loại vàng"].astype(str).str.contains("1L", na=False)]

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
                if len(cols) >= 2 and "SJC 1L" in cols[0].get_text():
                    price_text = cols[1].get_text().strip()
                    buy_str, sell_str = price_text.split(" / ")
                    buy_price = float(int(buy_str.replace(",", "")))
                    sell_price = float(int(sell_str.replace(",", "")))
                    print(f"Fetched fallback prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")
                    return buy_price, sell_price, date_str
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
        print("Source: vnstock + https://sjc.com.vn/")
        gold_data = fetch_sjc_with_retry(max_retries=10, delay=10)
        
        if gold_data is not None and len(gold_data) > 0:
            sjc_row = gold_data.iloc[0]
            buy_price = sjc_row.get('buy_price')
            sell_price = sjc_row.get('sell_price')

        if buy_price is None or sell_price is None:
            print("vnstock source unavailable, trying fallback source giavang.org...")
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
