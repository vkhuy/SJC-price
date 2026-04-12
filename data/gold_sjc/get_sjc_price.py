import os
import pandas as pd
from datetime import datetime
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

def fetch_and_save_sjc_price():   
    csv_file = 'sjc_final.csv'
    
    try:
        # Fetch SJC gold price data with retry
        print("Fetching SJC price...")
        print("Source: vnstock + https://sjc.com.vn/")
        gold_data = fetch_sjc_with_retry(max_retries=10, delay=10)
        
        if gold_data is None or len(gold_data) == 0:
            print("Failed to fetch SJC data after multiple attempts")
            return False
        
        sjc_row = gold_data.iloc[0]
        buy_price = sjc_row.get('buy_price')
        sell_price = sjc_row.get('sell_price')
        
        if buy_price is None or sell_price is None:
            print("Not Available SJC gold prices")
            return False

        print(f"Fetched prices: Buy={buy_price:,.0f} VND, Sell={sell_price:,.0f} VND")

        current_time = datetime.now()
        new_record = {
            'timestamp': current_time.strftime('%Y-%m-%d'),
            'buy_1l': round(buy_price / 1_000_000, 2),  # Convert from VND to million VND
            'sell_1l': round(sell_price / 1_000_000, 2)
        }

        # Read the current CSV file or create a new one
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
            print(f"Reading current file with {len(df)} records")
            
            # Check if today's record already exists (avoid duplicates)
            today = current_time.strftime('%Y-%m-%d')
            if today in df['timestamp'].values:
                print(f"Record for {today} already exists. Updating...")
                df.loc[df['timestamp'] == today, ['buy_1l', 'sell_1l']] = [new_record['buy_1l'], new_record['sell_1l']]
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