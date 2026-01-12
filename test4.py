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

# Tables to clean where `deleted_at` is not NULL
tables = [
    'clinics',
    'customers',
    'transactions',
    'users'
]

for table in tables:
    try:
        sql = f"DELETE FROM `{table}` WHERE deleted_at IS NOT NULL"
        mycursor.execute(sql)
        affected = mycursor.rowcount
        print(f"Deleted {affected} rows from {table} where deleted_at IS NOT NULL")
    except mysql.connector.Error as err:
        print(f"Error deleting from {table}: {err}")

db.commit()

mycursor.close()
db.close()
