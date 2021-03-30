import operator


def combine_dicts(a, b, op=operator.add):
    return {**a, **b, **{k: op(a[k], b[k]) for k in a.keys() & b.keys()}}
