# 函数与方法

函数是组织好的、可重复使用的代码块。学会使用函数可以让代码更清晰、更易于维护。

## 1. 什么是函数？

函数就像一台机器：给它输入，它给你输出。

```python
# 不使用函数（重复代码）
print("=" * 30)
print("欢迎光临")
print("=" * 30)

print("=" * 30)
print("谢谢惠顾")
print("=" * 30)

# 使用函数（简洁明了）
def print_banner(message):
    print("=" * 30)
    print(message)
    print("=" * 30)

print_banner("欢迎光临")
print_banner("谢谢惠顾")
```

## 2. 定义函数

### 2.1 基本语法

```python
def 函数名(参数1, 参数2, ...):
    """文档字符串（可选）"""
    # 函数体
    return 返回值  # 可选
```

### 2.2 简单示例

```python
# 无参数，无返回值
def greet():
    print("Hello!")

greet()  # 调用函数

# 有参数，无返回值
def greet_person(name):
    print(f"Hello, {name}!")

greet_person("张三")

# 有参数，有返回值
def add(a, b):
    return a + b

result = add(3, 5)
print(result)  # 8
```

## 3. 函数参数

### 3.1 位置参数

按顺序传递：

```python
def introduce(name, age, city):
    print(f"我是{name}，{age}岁，来自{city}")

introduce("张三", 18, "北京")  # 按顺序
```

### 3.2 关键字参数

按名称传递，顺序无所谓：

```python
def introduce(name, age, city):
    print(f"我是{name}，{age}岁，来自{city}")

introduce(age=18, city="北京", name="张三")  # 按名称
introduce("李四", city="上海", age=20)  # 混合使用
```

### 3.3 默认参数

参数有默认值：

```python
def greet(name, greeting="你好"):
    print(f"{greeting}, {name}!")

greet("张三")           # 你好, 张三!
greet("李四", "早上好")  # 早上好, 李四!
```

> **注意**：默认参数必须放在非默认参数后面

### 3.4 可变参数 *args

接收任意数量的位置参数：

```python
def calculate_sum(*numbers):
    total = 0
    for num in numbers:
        total += num
    return total

print(calculate_sum(1, 2, 3))        # 6
print(calculate_sum(1, 2, 3, 4, 5))  # 15
```

### 3.5 关键字可变参数 **kwargs

接收任意数量的关键字参数：

```python
def print_info(**info):
    for key, value in info.items():
        print(f"{key}: {value}")

print_info(name="张三", age=18, city="北京")
# 输出：
# name: 张三
# age: 18
# city: 北京
```

## 4. 返回值

### 4.1 return 语句

```python
def square(n):
    return n ** 2

result = square(5)
print(result)  # 25
```

### 4.2 返回多个值

```python
def get_min_max(numbers):
    return min(numbers), max(numbers)

minimum, maximum = get_min_max([3, 1, 4, 1, 5, 9])
print(f"最小值：{minimum}, 最大值：{maximum}")
# 最小值：1, 最大值：9
```

### 4.3 提前返回

```python
def find_first_even(numbers):
    for num in numbers:
        if num % 2 == 0:
            return num  # 找到就立即返回
    return None  # 没找到返回None

result = find_first_even([1, 3, 5, 6, 7])
print(result)  # 6
```

## 5. 变量作用域

### 5.1 局部变量和全局变量

```python
name = "全局变量"  # 全局变量

def my_function():
    name = "局部变量"  # 局部变量
    print(f"函数内：{name}")

my_function()           # 函数内：局部变量
print(f"函数外：{name}")  # 函数外：全局变量
```

### 5.2 global 关键字

在函数内修改全局变量：

```python
count = 0

def increment():
    global count  # 声明使用全局变量
    count += 1

increment()
increment()
print(count)  # 2
```

### 5.3 作用域规则 (LEGB)

Python查找变量的顺序：
1. **L**ocal（局部）
2. **E**nclosing（嵌套函数的外层）
3. **G**lobal（全局）
4. **B**uilt-in（内置）

```python
x = "global"

def outer():
    x = "enclosing"

    def inner():
        x = "local"
        print(x)  # local

    inner()
    print(x)  # enclosing

outer()
print(x)  # global
```

## 6. 常用内置函数

### 6.1 数学相关

```python
# 绝对值
print(abs(-5))      # 5

# 最大/最小值
print(max(1, 5, 3)) # 5
print(min(1, 5, 3)) # 1

# 求和
print(sum([1, 2, 3, 4, 5]))  # 15

# 四舍五入
print(round(3.7))    # 4
print(round(3.14159, 2))  # 3.14

# 幂运算
print(pow(2, 3))    # 8
```

### 6.2 类型转换

```python
print(int("123"))       # 123
print(float("3.14"))    # 3.14
print(str(123))         # "123"
print(bool(1))          # True
print(list("abc"))      # ['a', 'b', 'c']
```

### 6.3 序列相关

```python
# 长度
print(len([1, 2, 3]))   # 3

# 排序
print(sorted([3, 1, 4]))  # [1, 3, 4]

# 反转
print(list(reversed([1, 2, 3])))  # [3, 2, 1]

# 枚举
for i, v in enumerate(['a', 'b', 'c']):
    print(i, v)

# zip组合
names = ['张三', '李四']
ages = [18, 20]
for name, age in zip(names, ages):
    print(f"{name}: {age}岁")
```

### 6.4 输入输出

```python
# 输入
name = input("请输入姓名：")

# 输出
print("Hello", "World", sep="-", end="!\n")
```

## 7. Lambda 表达式

匿名函数，用于简单的单行函数：

```python
# 普通函数
def square(x):
    return x ** 2

# Lambda表达式
square = lambda x: x ** 2

print(square(5))  # 25

# 常与sorted()配合使用
students = [
    {"name": "张三", "score": 85},
    {"name": "李四", "score": 92},
    {"name": "王五", "score": 78}
]

# 按成绩排序
sorted_students = sorted(students, key=lambda s: s["score"], reverse=True)
for s in sorted_students:
    print(f"{s['name']}: {s['score']}")
```

## 8. 递归函数

函数调用自身：

```python
# 计算阶乘
def factorial(n):
    if n <= 1:  # 基本情况（递归出口）
        return 1
    return n * factorial(n - 1)  # 递归调用

print(factorial(5))  # 120 (5*4*3*2*1)

# 斐波那契数列
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(fibonacci(i), end=" ")
# 0 1 1 2 3 5 8 13 21 34
```

> **注意**：递归必须有终止条件，否则会无限递归导致程序崩溃。

## 9. 文档字符串

良好的函数应该有文档说明：

```python
def calculate_bmi(weight, height):
    """
    计算身体质量指数(BMI)

    参数:
        weight: 体重（公斤）
        height: 身高（米）

    返回:
        BMI值（浮点数）

    示例:
        >>> calculate_bmi(70, 1.75)
        22.86
    """
    return round(weight / (height ** 2), 2)

# 查看文档
print(calculate_bmi.__doc__)
help(calculate_bmi)
```

## 10. 常见错误与调试

### 错误1：忘记return

```python
def add(a, b):
    result = a + b
    # 忘记 return result

x = add(3, 5)
print(x)  # None
```

### 错误2：默认参数使用可变对象

```python
# 错误示例
def append_to(element, lst=[]):
    lst.append(element)
    return lst

print(append_to(1))  # [1]
print(append_to(2))  # [1, 2] 而不是 [2]！

# 正确做法
def append_to(element, lst=None):
    if lst is None:
        lst = []
    lst.append(element)
    return lst
```

### 错误3：参数顺序错误

```python
def divide(a, b):
    return a / b

# 注意参数顺序
print(divide(10, 2))  # 5.0
print(divide(2, 10))  # 0.2
```

## 小结

本章学习了：
- 函数的定义和调用
- 各种参数类型：位置参数、关键字参数、默认参数、*args、**kwargs
- 返回值和return语句
- 变量作用域（局部、全局、LEGB规则）
- 常用内置函数
- Lambda表达式
- 递归函数

**练习建议**：
1. 编写一个函数判断一个数是否为质数
2. 编写一个函数计算列表中所有数字的平均值
3. 用递归实现求最大公约数（辗转相除法）
