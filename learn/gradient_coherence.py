"""
https://blif.org/~satrajit/cg/

I want to validate the claim:

    However, by dividing the average dot product by the average norm of the
    per-example gradients, we get a metric (denoted by α) that is always
    between 0 and 1 where 1 indicates perfect coherence.
"""

import sympy
from itertools import combinations

dimensions = 1
scalars_a = sympy.symbols([f'a_{i}' for i in range(dimensions)])
scalars_b = sympy.symbols([f'b_{i}' for i in range(dimensions)])
scalars_c = sympy.symbols([f'c_{i}' for i in range(dimensions)])
scalars_d = sympy.symbols([f'd_{i}' for i in range(dimensions)])

A = sympy.Array(scalars_a)
B = sympy.Array(scalars_b)
C = sympy.Array(scalars_c)
D = sympy.Array(scalars_d)

vectors = {'A': A, 'B': B, 'C': C, 'D': D}
dot_products = {}
norms = {}

for k, V in vectors.items():
    # Compute L2 norm of each vector
    norms[k] = sympy.sqrt(sum([v ** 2 for v in V]))

for k1, k2 in combinations(vectors, 2):
    V1 = vectors[k1]
    V2 = vectors[k2]
    dot_products[(k1, k2)] = sum(v1 * v2 for v1, v2 in zip(V1, V2))

avg_dot = sum(dot_products.values()) / len(dot_products)
avg_norm = sum(norms.values()) / len(norms)

# TODO: how do we check this claim? Do we need to go into lean?

avg_dot - avg_norm

sympy.pprint(avg_dot)
sympy.pprint(avg_norm)
# sympy.pprint(sympy.simplify(avg_norm ** 2))

# sympy.simplify(avg_norm ** 2)
# sympy.simplify(avg_dot ** 2 - avg_norm ** 2)
