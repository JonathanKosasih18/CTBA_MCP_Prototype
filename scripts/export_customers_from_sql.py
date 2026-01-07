import re
import csv
from pathlib import Path


def extract_top_level_tuples(s: str):
    tuples = []
    i = 0
    n = len(s)
    in_str = False
    start = None
    depth = 0
    while i < n:
        ch = s[i]
        if ch == "'":
            if in_str:
                # handle escaped single-quote by doubling
                if i + 1 < n and s[i + 1] == "'":
                    i += 2
                    continue
                in_str = False
                i += 1
                continue
            else:
                in_str = True
                i += 1
                continue

        if not in_str:
            if ch == '(':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and start is not None:
                    tuples.append(s[start:i+1])
                    start = None
        i += 1
    return tuples


def split_fields(tuple_str: str):
    # Remove outer parentheses
    if tuple_str.startswith('(') and tuple_str.endswith(')'):
        inner = tuple_str[1:-1]
    else:
        inner = tuple_str
    fields = []
    buf = []
    in_str = False
    i = 0
    n = len(inner)
    while i < n:
        ch = inner[i]
        if ch == "'":
            # handle string and doubled single-quote as escape
            if in_str:
                if i + 1 < n and inner[i+1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_str = False
                i += 1
                continue
            else:
                in_str = True
                i += 1
                continue

        if not in_str and ch == ',':
            fields.append(''.join(buf).strip())
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    if buf:
        fields.append(''.join(buf).strip())

    return fields


def unquote_sql_value(val: str):
    if val is None:
        return ''
    v = val.strip()
    if v.upper() == 'NULL':
        return ''
    if v.startswith("'") and v.endswith("'"):
        inner = v[1:-1]
        # unescape doubled single-quotes
        return inner.replace("''", "'")
    return v


def main():
    workspace = Path(__file__).resolve().parents[1]
    sql_path = workspace / 'real_data.sql'
    out_csv = workspace / 'customers.csv'

    if not sql_path.exists():
        print(f"{sql_path} not found")
        return

    text = sql_path.read_text(encoding='utf-8', errors='ignore')

    # find all INSERT INTO `customers` ... VALUES ...; blocks
    inserts = re.findall(r"INSERT INTO `customers`.*?VALUES(.*?);", text, flags=re.S | re.I)

    rows = []
    for block in inserts:
        tuples = extract_top_level_tuples(block)
        for t in tuples:
            fields = split_fields(t)
            # indexes based on the INSERT field order in the dump
            # id=0, custname=2, phone=7
            if len(fields) >= 8:
                idv = unquote_sql_value(fields[0])
                name = unquote_sql_value(fields[2])
                phone = unquote_sql_value(fields[7])
                rows.append((idv, name, phone))

    # write CSV (overwrite)
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'custname', 'phone'])
        for r in rows:
            writer.writerow(r)

    print(f"Wrote {len(rows)} rows to {out_csv}")


if __name__ == '__main__':
    main()
