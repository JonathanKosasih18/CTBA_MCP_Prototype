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
mycursor.execute('SELECT daya_beli, COUNT(*) FROM customers GROUP BY daya_beli')
results = mycursor.fetchall()

for (daya_beli, count) in results:
    print(f'Daya Beli: {daya_beli}, Count: {count}')