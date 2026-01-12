import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
MY_PASSWORD = os.getenv('DB_PASSWORD')

# Initialize connection
db = mysql.connector.connect(
    host='localhost',
    user='root',
    password=MY_PASSWORD,
    database='ctba_real_db'
)

mycursor = db.cursor()
mycursor.execute("""
SELECT item_id, product, SUM(qty) as units, SUM(amount) as revenue 
        FROM transactions 
        GROUP BY item_id, product
""")
results = mycursor.fetchall()
for row in results:
    print(row)