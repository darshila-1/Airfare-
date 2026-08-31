import psycopg

# Your connection string from Supabase Project Settings -> Database -> Connection String (URI)
DB_URI = "postgresql://postgres:KAASUKABE12@db.simqhwgdwnffovehxplg.supabase.co:5432/postgres"

def insert_sample_raw_data():
    sample_data = {
        "route_id": "BOM-DEL",
        "origin": "BOM",
        "destination": "DEL",
        "airline": "IndiGo",
        "flight_number": "6E-205",
        "departure_time": "2026-09-15 10:30:00+05:30",
        "arrival_time": "2026-09-15 12:45:00+05:30",
        "price": 4500.00,
        "is_sold_out": False
    }

    # Connect using a context manager (auto-closes connection when finished)
    with psycopg.connect(DB_URI) as conn:
        with conn.cursor() as cur:
            insert_query = """
                INSERT INTO raw_fare_observations (
                    route_id, origin, destination, airline, 
                    flight_number, departure_time, arrival_time, price, is_sold_out
                ) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING raw_id;
            """
            
            cur.execute(insert_query, (
                sample_data["route_id"],
                sample_data["origin"],
                sample_data["destination"],
                sample_data["airline"],
                sample_data["flight_number"],
                sample_data["departure_time"],
                sample_data["arrival_time"],
                sample_data["price"],
                sample_data["is_sold_out"]
            ))
            
            inserted_id = cur.fetchone()[0]
            conn.commit()
            print(f"Success! Sample record inserted with raw_id: {inserted_id}")

if __name__ == "__main__":
    insert_sample_raw_data()