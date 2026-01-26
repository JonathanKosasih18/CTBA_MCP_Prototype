import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()
PASSWORD = os.getenv('DB_PASSWORD')

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password=PASSWORD, 
    database="ctba_db"
)

mycursor = db.cursor()

sql_folder = os.path.join(os.path.dirname(__file__), '../db')

# Specify the SQL file name to execute
sql_file_name = "ctba_real_db_users.sql"
file_path = os.path.join(sql_folder, sql_file_name)

if os.path.exists(file_path) and file_path.endswith('.sql'):
    with open(file_path, 'r', encoding='utf-8') as file:
        sql_script = file.read()
        mycursor.execute(sql_script)
    print(f"Executed {sql_file_name}")
else:
    print(f"File not found: {sql_file_name}")