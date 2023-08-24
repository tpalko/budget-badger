import re 
import sys 
import logging 

logger = logging.getLogger(__name__)

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
def get_records_from_csv(data, columns, header_included):
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
    start_line = 1 if header_included else 0
    lines = data.decode('utf-8').split('\n')[start_line:]

    logger.info(f'data has {len(lines)} lines, header included {header_included}')

    for partial in [ l for l in lines if l ]:

        line = f'{line}{partial}'        

        try:
            commas = _findstarts(line, ',')
            # -- the number of commas in the line must be at least the number of columns minus one 
            # -- there may be more, e.g. commas within quoted strings 
            if len(commas) <= 1 and len(records) == len(lines):
                logger.info(f'nothing on this line, but we have all the records')
                break 

            if len(commas) + 1 < len(columns):
                logger.debug(f'line: {line}')
                logger.debug(f'lines {len(lines)}, records: {len(records)}')
                raise Exception(f'The accumulated line so far has {len(commas) + 1} fields but we are parsing {len(columns)} columns')
            # -- so we find the quoted strings
            quotepairs = [ (l, r,) for l, r in _stepwise(_findstarts(line, '"'), take=2) ]
            items = []
            lastcomma = 0
            for comma in commas:
                # -- and ignore the commas within them 
                if _betweens(comma, quotepairs):
                    continue
                # -- okay, a real value-delimiting comma
                next = line[lastcomma:comma].strip()
                lastcomma = comma + 1                
                next_item = next.replace('"', '')
                # logger.debug(f'next item: {next_item}')
                items.append(next_item)
            items.append(line[lastcomma:].strip())
            if any(items):
                logger.debug(f'adding {",".join(items)} as a record')
                records.append(dict(zip(columns, items)))
            else:
                logger.debug(f'no items found on this line')
            line = ""
        except:
            logger.warning(sys.exc_info()[1])            
    
    return records 
