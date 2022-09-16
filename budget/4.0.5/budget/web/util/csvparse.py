import re 

def _betweens(thing, quotepairs):
    return any([ True for l,r in quotepairs if thing > l and thing < r ])

def _findstarts(line, c):
    ''''''
    return [ t.start() for t in re.finditer(c, line) ]

def _stepwise(items, start=0, step=1, take=1):
    ret = []
    while True:
        if start >= len(items):
            while len(ret) < take:
                ret.append(None)
            break
        ret.append(items[start])
        if len(ret) == take:
            yield ret 
            ret = []
        start += step 
    if any(ret):
        yield ret 

# '"Transaction Type"', '"Date"', '"Account Type"', '"Description"', '"Amount"', '"Reference No."', '"Credits"', '"Debits"']
def get_records_from_csv(data, columns):
    '''
    08/24/2022,APPLE.COM/BILL      INTERNET CHARGE     CA,5.34,"MM23Q73L5ZA RECORD STORE
    APPLE.COM/BILL
    INTERNET CHARGE
    CA
    RECORD STORE",APPLE.COM/BILL      INTERNET CHARGE     CA,One Apple Park Way,"Cupertino
    CA",95014,UNITED STATES,'320222370916290963',Merchandise & Supplies-Internet Purchase
    '''
    records = []
    line = ""
    for partial in data.decode('utf-8').split('\n')[1:]:
        line = f'{line}{partial}'
        print(f'parsing {line}')

        try:
            commas = _findstarts(line, ',')
            if len(commas) + 1 < len(columns):
                raise Exception(f'The accumulated line so far has {len(commas) + 1} fields but we are parsing {len(columns)} columns')
            quotepairs = [ (l, r,) for l, r in _stepwise(_findstarts(line, '"'), take=2) ]
            items = []
            lastcomma = 0
            for comma in commas:
                if _betweens(comma, quotepairs):
                    continue
                next = line[lastcomma:comma].strip()
                lastcomma = comma + 1
                items.append(next.replace('"', ''))
            items.append(line[lastcomma:].strip())
            if any(items):
                records.append(dict(zip(columns, items)))
            line = ""
        except:
            print(f'well that sucked, go get another partial and try again')
    
    return records 
