import os
import re
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

def execute_sql_file(filename):
    file_path = os.path.join(os.path.dirname(__file__), filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_file = f.read()

        # 1. Remove single-line comments (-- comment)
        sql_file = re.sub(r'--.*?\n', '', sql_file)
        
        # 2. Remove multi-line comments (/* comment */)
        sql_file = re.sub(r'/\*.*?\*/', '', sql_file, flags=re.DOTALL)

        # 3. Split by semicolon and filter out empty commands
        sql_commands = [cmd.strip() for cmd in sql_file.split(';') if cmd.strip()]

        for command in sql_commands:
            try:
                mycursor.execute(command)
            except mysql.connector.Error as err:
                print(f"Failed at command: {command[:50]}...")
                print(f"Error: {err}")
                raise # Re-raise to trigger the outer rollback

        db.commit()
        print(f"Successfully executed: {filename}")

    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()

# Run it!
execute_sql_file('acc_customers.sql')

# Clean up
mycursor.close()
db.close()