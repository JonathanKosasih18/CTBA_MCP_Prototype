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
mycursor.execute('SELECT c.custname, SUM(t.amount), t.salesman_name FROM transactions t JOIN acc_customers a ON t.cust_id = a.cid JOIN customers c ON a.custname = c.custname GROUP BY c.custname, t.salesman_name')
results = mycursor.fetchall()

for row in results:
    print(row)