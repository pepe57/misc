import sympy
from sympy import symbols, Matrix
from sympy import pprint
# https://www.reddit.com/r/MathJokes/comments/1ovyd0x/help_him/


# Define symbols
a1, b1, c1, d1 = symbols('a1 b1 c1 d1')
a2, b2, c2, d2 = symbols('a2 b2 c2 d2')

# Define the matrices
M1 = Matrix([[a1, b1],
             [c1, d1]])

M2 = Matrix([[a2, b2],
             [c2, d2]])

# Multiply them
result = M1 * M2

# Display the result
pprint(result)

pprint(result.subs({c1: 0, c2: 0}))

with sympy.evaluate(False):
    subed = result.subs({
        a1: 3, b1: 6,
        c1: 0, d1: 1,

        a2: 5, b2: 4,
        c2: 0, d2: 2
    })
    pprint(subed)
