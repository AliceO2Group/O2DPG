
""" FormulaLinearModel.py
import sys,os; sys.path.insert(1, os.environ[f"O2DPG"]+"/UTILS/dfextensions");
from  FormulaLinearModel import *
Utility helpers extension for FormulaLinearModel.py
"""


import ast
import numpy as np
from sklearn.linear_model import LinearRegression

class FormulaLinearModel:
    def __init__(self, name, formulas, target, precision=4, weight_formula=None, var_list=None):
        """
        Formula-based linear regression model supporting code export.

        :param name: name of the model (used for function naming)
        :param formulas: dict of {name: formula_string}, e.g., {'x1': 'v0*var00', 'x2': 'w1*var10'}
        :param target: string expression for target variable, e.g., 'log(y)' or 'y'
        :param precision: number of significant digits in code export (default: 4)
        :param weight_formula: optional string formula for sample weights
        :param var_list: optional list of variable names to fix the argument order for C++/JS export

        Example usage:

        >>> formulas = {'x1': 'v0*var00', 'x2': 'w1*var10'}
        >>> model = FormulaLinearModel("myModel", formulas, target='y')
        >>> model.fit(df)
        >>> df['y_pred'] = model.predict(df)
        >>> print(model.to_cpp())
        >>> print(model.to_pandas())
        >>> print(model.to_javascript())
        """
        self.name = name
        self.formulas = formulas
        self.target = target
        self.precision = precision
        self.weight_formula = weight_formula
        self.model = LinearRegression()
        self.feature_names = list(formulas.keys())

        extracted_vars = self._extract_variables(from_formulas_only=True)
        if var_list:
            missing = set(extracted_vars) - set(var_list)
            if missing:
                raise ValueError(f"Provided var_list is missing variables: {missing}")
            self.variables = var_list
        else:
            self.variables = sorted(extracted_vars)

    def _extract_variables(self, debug=False, from_formulas_only=False):
        class VarExtractor(ast.NodeVisitor):
            def __init__(self):
                self.vars = set()
                self.funcs = set()

            def visit_Name(self, node):
                self.vars.add(node.id)

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    self.funcs.add(node.func.id)
                self.generic_visit(node)

        extractor = VarExtractor()
        if from_formulas_only:
            all_exprs = list(self.formulas.values())
        else:
            all_exprs = list(self.formulas.values())
            if self.weight_formula:
                all_exprs.append(self.weight_formula)
            if isinstance(self.target, str):
                all_exprs.append(self.target)

        for expr in all_exprs:
            tree = ast.parse(expr, mode='eval')
            extractor.visit(tree)

        if debug:
            print("Detected variables:", extractor.vars)
            print("Detected functions:", extractor.funcs)

        return extractor.vars - extractor.funcs

    def fit(self, df):
        X = np.column_stack([df.eval(expr) for expr in self.formulas.values()])
        y = df.eval(self.target) if isinstance(self.target, str) else df[self.target]
        if self.weight_formula:
            sample_weight = df.eval(self.weight_formula).values
            self.model.fit(X, y, sample_weight=sample_weight)
        else:
            self.model.fit(X, y)

    def predict(self, df):
        X = np.column_stack([df.eval(expr) for expr in self.formulas.values()])
        mask_valid = ~np.isnan(X).any(axis=1)
        y_pred = np.full(len(df), np.nan)
        y_pred[mask_valid] = self.model.predict(X[mask_valid])
        return y_pred

    def coef_dict(self):
        return dict(zip(self.feature_names, self.model.coef_)), self.model.intercept_

    def to_cpp(self):
        fmt = f"{{0:.{self.precision}g}}"
        coefs, intercept = self.coef_dict()
        terms = [f"({fmt.format(coef)})*({self.formulas[name]})" for name, coef in coefs.items()]
        expr = " + ".join(terms) + f" + ({fmt.format(intercept)})"
        args = ", ".join([f"float {var}" for var in self.variables])
        return f"float {self.name}({args}) {{ return {expr}; }}"

    def to_pandas(self):
        fmt = f"{{0:.{self.precision}g}}"
        coefs, intercept = self.coef_dict()
        terms = [f"({fmt.format(coef)})*({expr})" for expr, coef in zip(self.formulas.values(), coefs.values())]
        return " + ".join(terms) + f" + ({fmt.format(intercept)})"

    def to_javascript(self):
        fmt = f"{{0:.{self.precision}g}}"
        coefs, intercept = self.coef_dict()
        terms = [f"({fmt.format(coef)})*({self.formulas[name]})" for name, coef in coefs.items()]
        expr = " + ".join(terms) + f" + ({fmt.format(intercept)})"
        args = ", ".join(self.variables)
        return f"function {self.name}({args}) {{ return {expr}; }}"

    def to_cppstd(self, name, variables, expression, precision=6):
        args = ", ".join([f"const std::vector<float>& {v}" for v in variables])
        output = [f"std::vector<float> {name}(size_t n, {args}) {{"]
        output.append(f"  std::vector<float> result(n);")
        output.append(f"  for (size_t i = 0; i < n; ++i) {{")
        for v in variables:
            output.append(f"    float {v}_i = {v}[i];")
        expr_cpp = expression
        for v in variables:
            expr_cpp = expr_cpp.replace(v, f"{v}_i")
        output.append(f"    result[i] = {expr_cpp};")
        output.append("  }")
        output.append("  return result;")
        output.append("}")
        return "\n".join(output)


    def to_cpparrow(self, name, variables, expression, precision=6):
        args = ", ".join([f"const arrow::FloatArray& {v}" for v in variables])
        output = [f"std::shared_ptr<arrow::FloatArray> {name}(int64_t n, {args}, arrow::MemoryPool* pool) {{"]
        output.append(f"  arrow::FloatBuilder builder(pool);")
        output.append(f"  builder.Reserve(n);")
        output.append(f"  for (int64_t i = 0; i < n; ++i) {{")
        expr_cpp = expression
        for v in variables:
            output.append(f"    float {v}_i = {v}.Value(i);")
            expr_cpp = expr_cpp.replace(v, f"{v}_i")
        output.append(f"    builder.UnsafeAppend({expr_cpp});")
        output.append("  }")
        output.append("  std::shared_ptr<arrow::FloatArray> result;")
        output.append("  builder.Finish(&result);")
        output.append("  return result;")
        output.append("}")
        return "\n".join(output)


