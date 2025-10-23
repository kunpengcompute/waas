IPC_VAL_MAX = 4.0
CPU_NUM_MAX = 256

class _cal:
    def __init__(self, x1, *args):
        self.x1 = x1
        self.extra = args

    def __call__(self, data):
        pass

    def __add__(self, other):
        return _Combined(self, other, lambda a, b: a + b)

    def __sub__(self, other):
        return _Combined(self, other, lambda a, b: a - b)

    def __mul__(self, other):
        return _Combined(self, other, lambda a, b: a * b)

    def __truediv__(self, other):
        return _Combined(self, other, lambda a, b: a / b if b != 0 else 0)

    def __floordiv__(self, other):
        return _Combined(self, other, lambda a, b: a // b if b != 0 else 0)

    def __mod__(self, other):
        return _Combined(self, other, lambda a, b: a % b if b != 0 else 0)

    def __pow__(self, other):
        return _Combined(self, other, lambda a, b: a ** b)

class _add(_cal):
    def __call__(self, data):
        extra_vals = [data[key] for key in self.extra]
        return data[self.x1] + sum(extra_vals)

class _sub(_cal):
    def __call__(self, data):
        if len(self.extra) < 1:
            return Exception("Parameters not enough to perform subtraction")
        return data[self.x1] - data[self.extra[0]]

def _mul(_cal):
    def __call__(self, data):
        if len(self.extra) < 1:
            return Exception("Parameters not enough to perform multiplication")
        return data[self.x1] * data[self.extra[0]]

class _div(_cal):
    def __call__(self, data):
        if len(self.extra) < 1:
            return Exception("No Denominator Provided.")
        if data[self.extra[0]] == 0:
            return 0
        return data[self.x1] / data[self.extra[0]]

class _cpy(_cal):
    def __call__(self, data):
        return data[self.x1]

class _Combined(_cal):
    def __init__(self, left, right, func):
        self.left = left
        self.right = right
        self.func = func

    def __call__(self, data):
        left_val = self.left
        if isinstance(self.left, _cal):
            left_val = self.left(data)

        right_val = self.right
        if isinstance(self.right, _cal):
            right_val = self.right(data)

        try:
            return self.func(left_val, right_val)
        except Exception as exp:
            raise exp