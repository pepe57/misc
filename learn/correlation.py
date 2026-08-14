import sympy as sp


def symbolic_correlation_full():
    # Define the length of the arrays
    n = sp.symbols('n', integer=True, positive=True)

    # Create symbolic variables for the two arrays
    values1 = sp.IndexedBase('X1')
    values2 = sp.IndexedBase('X2')

    # Define the elements of the arrays as symbolic variables
    i = sp.Idx('i', (0, n - 1))

    # Compute the mean of each array
    mean1 = sp.Sum(values1[i], (i, 0, n - 1)) / n
    mean2 = sp.Sum(values2[i], (i, 0, n - 1)) / n

    # Compute the numerator (covariance)
    covariance = sp.Sum((values1[i] - mean1) * (values2[i] - mean2), (i, 0, n - 1)) / n

    # Compute the denominators (standard deviations)
    std_dev1 = sp.sqrt(sp.Sum((values1[i] - mean1)**2, (i, 0, n - 1)))
    std_dev2 = sp.sqrt(sp.Sum((values2[i] - mean2)**2, (i, 0, n - 1)))

    # Compute the correlation coefficient
    correlation_coefficient = covariance / (std_dev1 * std_dev2)

    # Simplify the result if possible
    correlation_coefficient_simplified = sp.simplify(correlation_coefficient)

    print("Correlation coefficient:")
    print(correlation_coefficient_simplified)
    print(sp.pretty(correlation_coefficient_simplified))


def symbolic_correlation_with_symbolic_meanstd():
    # Define the length of the arrays
    n = sp.symbols('n', integer=True, positive=True)

    # Create symbolic variables for the two arrays
    values1 = sp.IndexedBase('X1')
    values2 = sp.IndexedBase('X2')

    # Define the elements of the arrays as symbolic variables
    i = sp.Idx('i', (0, n - 1))

    # Define symbolic means and standard deviations
    mean1 = sp.symbols('μ1')
    mean2 = sp.symbols('μ2')
    std_dev1 = sp.symbols('σ1', positive=True)
    std_dev2 = sp.symbols('σ2', positive=True)

    # Compute the covariance
    covariance = sp.Sum((values1[i] - mean1) * (values2[i] - mean2), (i, 0, n - 1)) / n

    # Compute the correlation coefficient
    correlation_coefficient = covariance / (std_dev1 * std_dev2)

    print("Correlation coefficient:")
    print(correlation_coefficient)
    print(sp.pretty(correlation_coefficient))


def symbolic_log_correlation_full():
    # Define the length of the arrays
    n = sp.symbols('n', integer=True, positive=True)

    # Create symbolic variables for the two arrays
    values1 = sp.IndexedBase('X1')
    values2 = sp.IndexedBase('X2')

    # Define the elements of the arrays as symbolic variables
    i = sp.Idx('i', (0, n - 1))

    log_values1 = sp.log(values1[i])
    log_values2 = sp.log(values2[i])

    # Compute the mean of each array
    mean1 = sp.Sum(log_values1, (i, 0, n - 1)) / n
    mean2 = sp.Sum(log_values2, (i, 0, n - 1)) / n

    # Compute the numerator (covariance)
    covariance = sp.Sum((log_values1 - mean1) * (log_values2 - mean2), (i, 0, n - 1))

    # Compute the denominators (standard deviations)
    std_dev1 = sp.sqrt(sp.Sum((log_values1 - mean1)**2, (i, 0, n - 1)))
    std_dev2 = sp.sqrt(sp.Sum((log_values2 - mean2)**2, (i, 0, n - 1)))

    # Compute the correlation coefficient
    correlation_coefficient = covariance / (std_dev1 * std_dev2)

    # Simplify the result if possible
    correlation_coefficient_simplified = sp.simplify(correlation_coefficient)

    print("Correlation coefficient:")
    print(correlation_coefficient_simplified)
    print(sp.pretty(correlation_coefficient_simplified))


def correlation_example():
    import numpy as np
    import kwarray

    var_modifiers = {
        'identity': lambda x: x,
        'scale': lambda x: x * 42,
        'neg_scale': lambda x: x * -42,
        'shift': lambda x: x + 42,
        'log': lambda x: np.log10(x),
        'square': lambda x: x ** 2,
    }
    n = 3

    rows = []
    for modifier_name, modifier_func in var_modifiers.items():
        rng = kwarray.ensure_rng(3213210)
        values1 = (rng.rand(n) > 0.5).astype(np.float64)
        values2 = (values1 + (rng.randn(n) ** 2)) + 0.1

        # values1 = np.array([0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0])
        # values2 = np.array([0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1]) * 10 + 0.1

        # values1 = np.array([modifier_func(x) for x in values1])
        values2 = np.array([modifier_func(x) for x in values2])

        mean1 = np.mean(values1)
        mean2 = np.mean(values2)
        std1 = np.std(values1)
        std2 = np.std(values2)
        cov = np.mean((values1 - mean1) * (values2 - mean2))
        corr = cov / (std1 * std2)

        row = {
            'modifier': modifier_name,
            'mean1': mean1,
            'mean2': mean2,
            'std1': std1,
            'std2': std2,
            'cov': cov,
            'corr': corr,
        }
        rows.append(row)

    import pandas as pd
    import rich
    table = pd.DataFrame(rows)
    rich.print(table)

    # nps = {
    #     'cov': np.cov(values1, values2, bias=True)[1, 0],
    #     'corr': np.corrcoef(values1, values2)[1, 0],
    # }
    # print(f'ours = {ub.urepr(ours, nl=1)}')
    # print(f'nps = {ub.urepr(nps, nl=1)}')


def symbolic_correlation_few_vars():
    """
    Given a fixed set of variables view differenec in correlation based
    on modification to underlying values.
    """
    import sympy as sp

    # Number of variables
    n = 3

    C = sp.symbols('C', real=True)

    var_modifiers = {
        'identity': lambda x: x,
        'scale': lambda x: x * C,
        'shift': lambda x: x + C,
        'log': lambda x: sp.log(x),
        'square': lambda x: x ** 2,
    }

    for modifier_name, modifier_func in var_modifiers.items():
        print('')
        print(f'--- {modifier_name} ---')

        xs = sp.symbols([f'x{i}' for i in range(1, n + 1)], real=True)
        ys = sp.symbols([f'y{i}' for i in range(1, n + 1)], real=True)

        xs = [modifier_func(x) for x in xs]
        # ys = [modifier_func(y) for y in ys]

        # Compute means
        mean1 = sum(xs) / n
        mean2 = sum(ys) / n

        # Compute variance and standard deviations
        var1 = sum([(x - mean1) ** 2 for x in xs]) / n
        var2 = sum([(y - mean2) ** 2 for y in ys]) / n
        std1 = sp.sqrt(var1)
        std2 = sp.sqrt(var2)

        # Covariance
        cov = sum([(x - mean1) * (y - mean2) for x, y in zip(xs, ys)]) / n

        # Compute the correlation coefficient
        corr = cov / (std1 * std2)
        # print(sp.pretty(corr))

        # Simplify the result if possible
        corr_simple = sp.simplify(corr)

        print("Correlation coefficient:")
        print(sp.pretty(corr_simple))
