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
mycursor.execute('SELECT SUM(qty) as total_qty, SUM(amount) as total_revenue FROM transactions WHERE inv_date BETWEEN "2024-10-01" AND "2024-09-30"')
result = mycursor.fetchone()
print(f"Total Quantity: {result[0]}, Total Revenue: {result[1]}")