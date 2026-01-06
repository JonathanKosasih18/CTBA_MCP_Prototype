import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
MY_PASSWORD = os.getenv('DB_PASSWORD')

# Initialize connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=MY_PASSWORD,
    database="ctba_real_db"
)

mycursor = db.cursor()

sql_path = os.path.join(os.path.dirname(__file__), 'real_data.sql')

try:
    with open(sql_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
 
    queries = [q.strip() for q in sql_content.split(';') if q.strip()]

    print(f"Found {len(queries)} queries. Starting execution...")

    for query in queries:
        try:
            mycursor.execute(query)
            
            # If the query returns data (like SELECT), we must fetch it to clear the buffer
            if mycursor.with_rows:
                mycursor.fetchall()
                
            print(f"Successfully executed: {query[:50]}...")
        except mysql.connector.Error as err:
            print(f"Failed to execute query: {err}")
            print(f"Query snippet: {query[:100]}")

    db.commit()
    print("\nDatabase update complete.")

except FileNotFoundError:
    print(f"Error: Could not find the file at {sql_path}")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    mycursor.close()
    db.close()