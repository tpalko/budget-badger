def tokenize_records(records):

    return set(" ".join([ r.description for r in records ]).split(' '))
    