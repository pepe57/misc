"""
Show the relationship between the F1 and Jaccard (IoU) scores.
"""
from sympy import symbols, Eq, solve, simplify
import sympy as sp

# Prove: IoU = F1 / (2 - F1)

# Step 1: Define symbols
TP, FP, FN = sp.symbols('TP FP FN', positive=True)

# Step 2: Define F1 and IoU
f1_expr = 2 * TP / (2 * TP + FP + FN)
iou_expr = TP / (TP + FP + FN)

# Step 3: Express F1 in terms of IoU
# Let’s define IoU = iou_sym and solve for TP
iou_sym = sp.symbols('iou_sym')
eq = sp.Eq(iou_sym, iou_expr)
tp_expr_in_terms_of_iou = sp.solve(eq, TP)[0]

# Step 4: Substitute TP into the F1 expression
f1_in_terms_of_iou = f1_expr.subs(TP, tp_expr_in_terms_of_iou)
f1_in_terms_of_iou = sp.simplify(f1_in_terms_of_iou)

# Step 5: Rearrange the result to match expected form
f1_final = sp.simplify(f1_in_terms_of_iou)

print("Proved: F1 in terms of IoU")
sp.pprint(sp.Eq(sp.symbols('F1'), f1_final))

# Now prove the inverse: IoU in terms of F1
f1_sym = sp.symbols('f1_sym')
eq2 = sp.Eq(f1_sym, f1_expr)
tp_expr_in_terms_of_f1 = sp.solve(eq2, TP)[0]

iou_in_terms_of_f1 = iou_expr.subs(TP, tp_expr_in_terms_of_f1)
iou_final = sp.simplify(iou_in_terms_of_f1)

print("\nProved: IoU in terms of F1")
sp.pprint(sp.Eq(sp.symbols('IoU'), iou_final))


# Maybe this lean4 code will work?
"""

import Mathlib.Data.Real.Basic
import Mathlib.Tactic

open Real

variable (tp fp fn : ℝ)
variable (hdenom1 : 2 * tp + fp + fn ≠ 0)
variable (hdenom2 : tp + fp + fn ≠ 0)

def f1 (tp fp fn : ℝ) : ℝ := 2 * tp / (2 * tp + fp + fn)
def iou (tp fp fn : ℝ) : ℝ := tp / (tp + fp + fn)

theorem f1_eq_2iou_div_1p_iou :
    f1 tp fp fn = (2 * iou tp fp fn) / (1 + iou tp fp fn) := by
  unfold f1 iou
  field_simp [hdenom1, hdenom2]
  -- Multiply both numerator and denominator by (tp + fp + fn)
  -- Goal becomes:
  -- (2 * tp) * (tp + fp + fn) = (2 * tp) * (tp + fp + fn)
  ring


"""

# Also prove PPV = (F1 * TPR) / (2 * TPR - F1)

# Define symbols
PPV, F1, TPR = symbols('PPV F1 TPR', positive=True)

# Start from the definition of F1-score:
# F1 = 2 * (PPV * TPR) / (PPV + TPR)
f1_expr = Eq(F1, 2 * (PPV * TPR) / (PPV + TPR))

# Solve this equation for PPV
ppv_solution = solve(f1_expr, PPV)[0]

# Simplify the result
ppv_simplified = simplify(ppv_solution)

# Compare with the desired expression
target_expr = (F1 * TPR) / (2 * TPR - F1)

# Check equality
is_equal = simplify(ppv_simplified - target_expr) == 0

# Output results
print(f"Solved PPV expression: {ppv_simplified}")
print(f"Target expression: {target_expr}")
print(f"Do they match? {'Yes' if is_equal else 'No'}")
