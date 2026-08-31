import psycopg

DB_URI = "postgresql://postgres.simqhwgdwnffovehxplg:KAASUKABE12@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

def calculate_benchmarks():
    with psycopg.connect(DB_URI) as conn:
        with conn.cursor() as cur:
            # Aggregate average price grouped by route and advance booking window
            query = """
                INSERT INTO reference_prices (route_id, advance_days, reference_price, sample_size)
                SELECT 
                    route_id,
                    advance_days,
                    ROUND(AVG(price)::numeric, 2) AS reference_price,
                    COUNT(*) AS sample_size
                FROM cleaned_fare_observations
                GROUP BY route_id, advance_days
                ON CONFLICT (route_id, advance_days) 
                DO UPDATE SET 
                    reference_price = EXCLUDED.reference_price,
                    sample_size = EXCLUDED.sample_size,
                    updated_at = NOW();
            """
            cur.execute(query)
            conn.commit()
            print("Successfully calculated and updated reference prices!")

if __name__ == "__main__":
    calculate_benchmarks()