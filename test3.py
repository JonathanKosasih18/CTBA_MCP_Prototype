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
mycursor.execute('DROP TABLE IF EXISTS acc_customers')
mycursor.execute('''
    CREATE TABLE `acc_customers` (
    `id` bigint(20) UNSIGNED NOT NULL PRIMARY KEY,
    `cid` varchar(255) NOT NULL,
    `cust_name` varchar(255) NOT NULL,
    `address1` varchar(255) DEFAULT NULL,
    `address2` varchar(255) DEFAULT NULL,
    `locality` varchar(255) DEFAULT NULL,
    `province` varchar(255) DEFAULT NULL,
    `city` varchar(255) DEFAULT NULL,
    `postal_code` varchar(255) DEFAULT NULL,
    `clasification` varchar(255) DEFAULT NULL,
    `dccode` varchar(255) DEFAULT NULL,
    `amcode` varchar(255) DEFAULT NULL,
    `tscode` varchar(255) DEFAULT NULL,
    `pscode` varchar(255) DEFAULT NULL,
    `smcode` varchar(255) DEFAULT NULL,
    `deleted_at` timestamp NULL DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT NULL,
    `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
''')