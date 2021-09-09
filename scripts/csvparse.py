import re 

def _betweens(thing, quotepairs):
    return any([ True for l,r in quotepairs if thing > l and thing < r ])

def _findstarts(line, c):
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
headers = ['type', 'date', 'account', 'description', 'amount', 'ref', 'credits', 'debits']
def get_records(data):
    records = []
    for line in data.split('\n')[1:]:
        commas = _findstarts(line, ',')
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
            records.append(dict(zip(headers, items)))
    for r in records:
        r['amount'] = float(r['amount'])
    return records 
