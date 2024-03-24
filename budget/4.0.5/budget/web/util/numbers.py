def _floatify(val):
    stripped_val = str(val).replace('$', '').replace(',', '').replace('"', '')
    mult = 1
    if len(stripped_val) > 2:        
        while stripped_val[0] == '-':
            mult *= -1
            stripped_val = stripped_val[1:]
    return float(stripped_val or 0)*mult