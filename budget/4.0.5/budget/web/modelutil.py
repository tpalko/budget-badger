from web.util.csvparse import get_records_from_csv
from datetime import datetime 

def choiceify(choices):
    return tuple([ [c, f'{c[0].upper()}{c[1:]}'] for c in choices ])

def _floatify(val):
    return float(val.replace('$', '').replace(',', '').replace('"', '') or 0.00)

def _process_records(records, csv_date_format):
    '''Field conversions, formatting (and potentially additions)'''

    records = [ {
        **record,
        'description': record['description'].replace('\t', '') if 'description' in record else record['name'].replace('\t', ''),
        'transaction_date': datetime.strptime(record['transaction_date'], csv_date_format) if 'transaction_date' in record else datetime.strptime(record['date'], csv_date_format),
        'post_date': datetime.strptime(record['post_date'], csv_date_format) if 'post_date' in record else datetime.strptime(record['date'], csv_date_format),
        'amount': _floatify(record['amount'] if 'amount' in record else record['gross'])
    } for record in records ]

    for record in records:
        for float_potential in ['credits', 'debits']:
            if float_potential in record:
                record[float_potential] = _floatify(record[float_potential])
    
    return records 

def process_uploaded_file(uploaded_file):
    '''Ingestion of CSV file to database'''

    file_contents = uploaded_file.upload.read()
    columns = uploaded_file.recordtype.csv_columns

    # -- do a little preprocessing so we can avoid duplicating uploaded files 
    records = _process_records(get_records_from_csv(file_contents, columns.split(',')), uploaded_file.recordtype.csv_date_format)
    records_dates = [ r['transaction_date'] for r in records ]
    first_date = min(records_dates)
    last_date = max(records_dates)

    return {
        'first_date': first_date,
        'last_date': last_date,
        'records': records
    } 
