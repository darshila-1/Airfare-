import psycopg
import pandas as pd

DB_URI = "postgresql://postgres.simqhwgdwnffovehxplg:KAASUKABE12@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

# Official 20 Representative Routes (10 bidirectional pairs)
ALLOWED_ROUTES = [
    "DEL-BOM", "BOM-DEL",
    "DEL-CCU", "CCU-DEL",
    "DEL-MAA", "MAA-DEL",
    "DEL-BLR", "BLR-DEL",
    "BLR-BOM", "BOM-BLR",
    "DEL-PNQ", "PNQ-DEL",
    "MAA-CCU", "CCU-MAA",
    "BHO-CCU", "CCU-BHO",
    "BOM-CCU", "CCU-BOM",
    "DEL-GOI", "GOI-DEL"
]

VALID_ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

def run_pipeline():
    with psycopg.connect(DB_URI) as conn:
        with conn.cursor() as cur:
            # 1. Fetch raw scraped observations from Supabase
            cur.execute("""
                SELECT id, route_id, origin, destination, departure_time, 
                       created_at, price, currency, is_sold_out 
                FROM raw_fare_observations;
            """)
            rows = cur.fetchall()
            
            if not rows:
                print("No raw observations found to process.")
                return

            columns = [
                'id', 'route_id', 'origin', 'destination', 'departure_time', 
                'created_at', 'price', 'currency', 'is_sold_out'
            ]
            df = pd.DataFrame(rows, columns=columns)
            total_raw = len(df)

            # 2. Sequential Validation & Data Audit Tracking
            
            # Check for missing critical fields (origin, destination, departure_time, price)
            df_no_missing = df.dropna(subset=['origin', 'destination', 'departure_time', 'price']).copy()
            missing_records = total_raw - len(df_no_missing)

            # Check for sold out flights
            sold_out_records = len(df_no_missing[df_no_missing['is_sold_out'] == True])
            df_valid = df_no_missing[df_no_missing['is_sold_out'] == False].copy()

            # Check for non-positive fares (price <= 0)
            invalid_records = len(df_valid[df_valid['price'] <= 0])
            df_valid = df_valid[df_valid['price'] > 0]

            # Validate currency
            df_valid = df_valid[df_valid['currency'].str.upper() == 'INR']

            # Validate against the 20 representative routes
            df_valid = df_valid[df_valid['route_id'].str.upper().isin(ALLOWED_ROUTES)]

            # Calculate advance booking window (in days)
            df_valid['departure_time'] = pd.to_datetime(df_valid['departure_time'])
            df_valid['created_at'] = pd.to_datetime(df_valid['created_at'])
            df_valid['advance_days'] = (df_valid['departure_time'] - df_valid['created_at']).dt.days

            # Filter strictly for 1, 7, 15, 30, and 45 advance window buckets
            df_valid = df_valid[df_valid['advance_days'].isin(VALID_ADVANCE_WINDOWS)]

            # Deduplication Check
            dedup_cols = ['route_id', 'departure_time']
            duplicates_removed = len(df_valid) - len(df_valid.drop_duplicates(subset=dedup_cols))
            df_clean = df_valid.drop_duplicates(subset=dedup_cols)

            # Outlier Flagging (> 100,000 INR)
            outliers_flagged = len(df_clean[df_clean['price'] > 100000])

            clean_records = len(df_clean)
            coverage_pct = round((clean_records / total_raw) * 100, 2) if total_raw > 0 else 0.0

            # 3. Write validated rows into cleaned_fare_observations
            insert_clean_query = """
                INSERT INTO cleaned_fare_observations (
                    raw_id, route_id, origin, destination, departure_time, 
                    price, currency, advance_days
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """
            for _, row in df_clean.iterrows():
                cur.execute(insert_clean_query, (
                    int(row['id']),
                    row['route_id'],
                    row['origin'],
                    row['destination'],
                    row['departure_time'],
                    float(row['price']),
                    row['currency'],
                    int(row['advance_days'])
                ))

            # 4. Write audit statistics into data_quality_runs
            insert_audit_query = """
                INSERT INTO data_quality_runs (
                    source, total_raw, duplicates_removed, invalid_records,
                    missing_records, sold_out_records, outliers_flagged,
                    clean_records, coverage_percentage
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
                RETURNING run_id;
            """
            cur.execute(insert_audit_query, (
                'SCRAPER_GOPAL', total_raw, duplicates_removed, invalid_records,
                missing_records, sold_out_records, outliers_flagged,
                clean_records, coverage_pct
            ))
            run_id = cur.fetchone()[0]

            conn.commit()

            print("--- DATA QUALITY METRICS ---")
            print(f"Total Raw: {total_raw} | Clean: {clean_records} | Duplicates Removed: {duplicates_removed}")
            print(f"Missing: {missing_records} | Invalid: {invalid_records} | Sold Out: {sold_out_records}")
            print(f"Coverage: {coverage_pct}%")
            print(f"Logged Data Quality Run ID: {run_id}")

if __name__ == "__main__":
    run_pipeline()