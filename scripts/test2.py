import os
import re
import mysql.connector
from dotenv import load_dotenv
from collections import Counter

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

def parse_sql_file(file_path):
    customers = {} # id -> name
    plans_counts = Counter() # customer_id -> count
    transactions_counts = Counter() # cust_id (CID...) -> count

    print(f"Reading {file_path}...")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split into statements using semicolon
    # This is a naive split but accurate enough for SQL dumps unless ; is in string
    statements = content.split(';')
    
    print(f"Parsing {len(statements)} statements...")
    
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt.upper().startswith("INSERT INTO"):
            continue
            
        # Match table name and columns
        # INSERT INTO `table` (`col1`, `col2`) VALUES
        header_match = re.match(r"INSERT INTO `(\w+)` \s*\((.*?)\)\s*VALUES", stmt, re.IGNORECASE | re.DOTALL)
        if not header_match:
            continue
            
        table = header_match.group(1).lower()
        if table not in ['customers', 'plans', 'transactions']:
            continue
            
        columns_str = header_match.group(2)
        columns = [c.strip().strip('`') for c in columns_str.split(',')]
        
        # Get values part
        values_part = stmt[header_match.end():].strip()
        
        # Parse values tuples
        # We need to iterate carefully.
        # Format is (val1, val2), (val3, val4)
        
        # Simple parser for values
        # We'll use a regex to capture each tuple (...)
        # WARNING: This regex might fail on complex nested parenthesis or strings with )
        # But standard SQL dumps usually structure nicely.
        # Let's assume standard structure: (..., ..., ...)
        
        # Using a simplistic manual parser is safer
        idx = 0
        length = len(values_part)
        
        while idx < length:
            # Find start of tuple
            start = values_part.find('(', idx)
            if start == -1:
                break
                
            # Find end of tuple. Must handle quotes.
            end = -1
            cursor = start + 1
            in_quote = False
            
            while cursor < length:
                char = values_part[cursor]
                if char == "'" and (cursor == 0 or values_part[cursor-1] != '\\'):
                    in_quote = not in_quote
                elif char == ')' and not in_quote:
                    end = cursor
                    break
                cursor += 1
            
            if end == -1:
                break
                
            # Extract tuple content
            tuple_content = values_part[start+1:end]
            
            # Parse fields
            fields = []
            f_cursor = 0
            f_len = len(tuple_content)
            current_field = []
            f_in_quote = False
            
            while f_cursor < f_len:
                char = tuple_content[f_cursor]
                if char == "'" and (f_cursor == 0 or tuple_content[f_cursor-1] != '\\'):
                    f_in_quote = not f_in_quote
                    current_field.append(char) # Keep quotes for now to identify strings
                elif char == ',' and not f_in_quote:
                    fields.append("".join(current_field).strip())
                    current_field = []
                else:
                    current_field.append(char)
                f_cursor += 1
            fields.append("".join(current_field).strip())
            
            # Clean fields
            clean_fields = []
            for field in fields:
                if field.startswith("'") and field.endswith("'"):
                    # String
                    val = field[1:-1].replace("\\'", "'").replace("\\n", "\n")
                    clean_fields.append(val)
                elif field.upper() == 'NULL':
                    clean_fields.append(None)
                else:
                    # Number
                    try:
                        clean_fields.append(int(field))
                    except:
                        clean_fields.append(field)
            
            # Map to columns
            if len(clean_fields) == len(columns):
                row = dict(zip(columns, clean_fields))
                
                if table == 'customers':
                    if 'id' in row and 'custname' in row:
                        customers[row['id']] = row['custname']
                elif table == 'plans':
                    if 'custcode' in row:
                        plans_counts[row['custcode']] += 1
                elif table == 'transactions':
                    if 'cust_id' in row:
                        transactions_counts[row['cust_id']] += 1
                        
            idx = end + 1
            # Skip comma and whitespace
            while idx < length and values_part[idx] in [',', ' ', '\n', '\r', '\t']:
                idx += 1

    return customers, plans_counts, transactions_counts

def generate():
    sql_path = os.path.join(os.path.dirname(__file__), 'real_data.sql')
    customers, plans_counts, transactions_counts = parse_sql_file(sql_path)
    
    print(f"Stats: {len(customers)} customers, {len(plans_counts)} visited, {len(transactions_counts)} transaction IDs.")

    # Sort Customers by visits
    cust_list = []
    for cid, name in customers.items():
        visits = plans_counts.get(cid, 0)
        cust_list.append({'name': name, 'visits': visits})
        
    cust_list.sort(key=lambda x: x['visits'], reverse=True)
    
    # Sort Transactions by count
    trans_list = []
    for tid, count in transactions_counts.items():
        if tid:
            trans_list.append({'tid': tid, 'count': count})
            
    trans_list.sort(key=lambda x: x['count'], reverse=True)
    
    # Map
    inserts = []
    for i, t_data in enumerate(trans_list):
        tid = t_data['tid']
        
        if i < len(cust_list):
            cust_name = cust_list[i]['name']
        else:
            cust_name = 'Anonymus'
            
        inserts.append((i+1, tid, cust_name))
        
    print(f"Prepared {len(inserts)} inserts for acc_customers.")
    # Debug top 5
    for k in range(min(5, len(inserts))):
        print(f"Rank {k+1}: {inserts[k]}")

    # DB Operations
    mycursor.execute("TRUNCATE TABLE acc_customers")
    
    sql = "INSERT INTO acc_customers (id, cid, cust_name) VALUES (%s, %s, %s)"
    batch_size = 500
    for i in range(0, len(inserts), batch_size):
        chunk = inserts[i:i+batch_size]
        mycursor.executemany(sql, chunk)
        db.commit()
        
    print("Insertion complete.")

if __name__ == "__main__":
    generate()
    mycursor.close()
    db.close()
