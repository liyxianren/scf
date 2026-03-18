# Python 基础语法

Python 是一种简单易学、功能强大的编程语言。本章将带你从零开始，学习 Python 的基础知识。

---

## 1. Python 简介

### 1.1 什么是 Python？

Python 是由 Guido van Rossum 于 1989 年发明的一种解释型、面向对象、动态数据类型的高级程序设计语言。

**Python 的特点：**
- **简单易学**：语法简洁清晰，接近自然语言
- **免费开源**：可以自由使用和分发
- **可移植性**：可在多种平台上运行（Windows、Linux、Mac）
- **丰富的库**：拥有大量的标准库和第三方库

### 1.2 Python 能做什么？

- **Web 开发**：Django、Flask 等框架
- **数据分析**：NumPy、Pandas、Matplotlib
- **人工智能**：TensorFlow、PyTorch
- **自动化脚本**：系统管理、文件处理
- **爬虫开发**：Scrapy、BeautifulSoup

---

## 2. 第一个 Python 程序

让我们从经典的 "Hello World" 开始：

```python
print("Hello, World!")
```

`print()` 是 Python 的内置函数，用于在屏幕上输出内容。

---

## 3. Python 编码

Python 3 源码文件默认使用 **UTF-8** 编码，所以可以直接使用中文：

```python
print("你好，Python！")
```

如果需要指定其他编码，可以在文件开头添加：

```python
# -*- coding: utf-8 -*-
```

---

## 4. 标识符

**标识符**是变量、函数、类等的名称。Python 标识符的命名规则：

1. 由字母、数字、下划线组成
2. **不能以数字开头**
3. **区分大小写**（`name` 和 `Name` 是不同的变量）
4. 不能使用 Python 保留字

```python
# 合法的标识符
name = "张三"
_age = 18
student1 = "李四"
myName = "王五"

# 不合法的标识符（会报错）
# 1name = "错误"    # 不能以数字开头
# my-name = "错误"  # 不能使用连字符
# class = "错误"    # 不能使用保留字
```

### 4.1 Python 保留字

保留字是 Python 语言已经定义好的、有特殊含义的标识符，不能用作变量名。

```python
# 查看 Python 所有保留字
import keyword
print(keyword.kwlist)
```

**常用保留字说明：**
| 保留字 | 说明 |
|--------|------|
| `True` / `False` | 布尔值真/假 |
| `None` | 空值 |
| `if` / `elif` / `else` | 条件判断 |
| `for` / `while` | 循环 |
| `def` | 定义函数 |
| `class` | 定义类 |
| `return` | 函数返回值 |
| `import` | 导入模块 |

---

## 5. 注释

注释是代码中的说明文字，不会被执行，用于提高代码可读性。

### 5.1 单行注释

使用 `#` 开头：

```python
# 这是一个单行注释
print("Hello")  # 这也是注释，在代码后面
```

### 5.2 多行注释

使用三个单引号 `'''` 或三个双引号 `"""`：

```python
'''
这是多行注释
可以写很多行
用于详细说明
'''

"""
这也是多行注释
使用双引号
效果一样
"""

print("注释不会被执行")
```

### 5.3 注释的作用

1. **解释代码**：说明代码的功能
2. **调试代码**：临时禁用某段代码
3. **生成文档**：文档字符串可自动生成文档

```python
def add(a, b):
    """
    计算两个数的和

    参数:
        a: 第一个数
        b: 第二个数

    返回:
        两数之和
    """
    return a + b
```

---

## 6. 行与缩进

Python 最具特色的就是使用**缩进**来表示代码块，而不是使用大括号 `{}`。

### 6.1 缩进规则

- 同一个代码块的缩进空格数必须相同
- 建议使用 **4 个空格**进行缩进
- 不要混用 Tab 和空格

```python
# 正确的缩进
if True:
    print("True")
    print("缩进正确")

# 错误的缩进（会报错）
# if True:
#     print("True")
#   print("缩进错误")  # IndentationError
```

### 6.2 多行语句

如果语句很长，可以使用反斜杠 `\` 换行：

```python
# 使用 \ 换行
total = 1 + 2 + 3 + \
        4 + 5 + 6 + \
        7 + 8 + 9
print(total)  # 45

# 在括号内可以直接换行，不需要 \
numbers = [1, 2, 3,
           4, 5, 6,
           7, 8, 9]
print(sum(numbers))
```

### 6.3 同一行多条语句

可以使用分号 `;` 在同一行写多条语句（但不推荐）：

```python
a = 1; b = 2; c = 3
print(a, b, c)  # 1 2 3
```

---

## 7. 变量

变量是存储数据的容器。在 Python 中，变量**不需要声明类型**，赋值时自动确定类型。

### 7.1 变量的创建

```python
# 创建变量
name = "张三"      # 字符串
age = 18          # 整数
height = 1.75     # 浮点数
is_student = True # 布尔值

print(name)       # 张三
print(age)        # 18
print(height)     # 1.75
print(is_student)
```

### 7.2 变量命名规范

**规则（必须遵守）：**
- 只能包含字母、数字、下划线
- 不能以数字开头
- 不能使用保留字

**规范（建议遵守）：**
- 使用有意义的名称
- 使用小写字母和下划线（蛇形命名法）
- 常量使用全大写

```python
# 好的命名
student_name = "张三"
total_score = 95
MAX_SIZE = 100  # 常量

# 不好的命名
a = "张三"      # 含义不明
studentName = "张三"  # 驼峰命名（Python 不推荐）
```

### 7.3 多变量赋值

Python 支持同时给多个变量赋值：

```python
# 同时给多个变量赋相同的值
a = b = c = 100
print(a, b, c)  # 100 100 100

# 同时给多个变量赋不同的值
x, y, z = 1, 2, 3
print(x, y, z)  # 1 2 3

# 交换两个变量的值
a, b = 10, 20
print(f"交换前: a={a}, b={b}")  # 交换前: a=10, b=20

a, b = b, a
print(f"交换后: a={a}, b={b}")
```

---

## 8. 数据类型

Python 中有以下基本数据类型：

| 类型 | 说明 | 示例 |
|------|------|------|
| `int` | 整数 | `10`, `-5`, `0` |
| `float` | 浮点数 | `3.14`, `-2.5`, `1.0` |
| `str` | 字符串 | `"hello"`, `'world'` |
| `bool` | 布尔值 | `True`, `False` |

### 8.1 整数 (int)

整数就是没有小数部分的数字，可以是正数、负数或零。

```python
# 整数示例
a = 100
b = -50
c = 0

print(a, type(a))  # 100 <class 'int'>
print(b, type(b))  # -50 <class 'int'>
print(c, type(c))
```

**不同进制表示：**

```python
# 十进制（默认）
num1 = 100
print(num1)  # 100

# 二进制（0b 开头）
num2 = 0b1010
print(num2)  # 10

# 八进制（0o 开头）
num3 = 0o12
print(num3)  # 10

# 十六进制（0x 开头）
num4 = 0xA
print(num4)
```

> **注意**：Python 3 的整数没有大小限制，可以表示任意大的数。

### 8.2 浮点数 (float)

浮点数就是带小数点的数字。

```python
# 浮点数示例
price = 19.99
pi = 3.14159
negative = -2.5

print(price, type(price))  # 19.99 <class 'float'>
print(pi, type(pi))        # 3.14159 <class 'float'>
print(negative, type(negative))
```

**科学计数法：**

```python
# 科学计数法表示
num1 = 1.5e3   # 1.5 × 10³ = 1500.0
num2 = 2.5e-2  # 2.5 × 10⁻² = 0.025

print(num1)
print(num2)
```

> **注意**：浮点数运算可能存在精度问题：
> ```python
> print(0.1 + 0.2)  # 0.30000000000000004
> ```

### 8.3 字符串 (str)

字符串是由字符组成的序列，用引号包围。

**创建字符串：**

```python
# 单引号
s1 = 'Hello'

# 双引号
s2 = "World"

# 三引号（可以包含换行）
s3 = '''这是
多行
字符串'''

s4 = """这也是
多行
字符串"""

print(s1)  # Hello
print(s2)  # World
print(s3)
print(s4)
```

**转义字符：**

| 转义字符 | 说明 |
|----------|------|
| `\n` | 换行 |
| `\t` | 制表符（Tab） |
| `\\` | 反斜杠 |
| `\'` | 单引号 |
| `\"` | 双引号 |

```python
print("Hello\nWorld")   # 换行
print("Hello\tWorld")   # 制表符
print("C:\\Users\\")    # 反斜杠
print('It\'s OK')
```

**字符串操作：**

```python
s = "Hello, Python!"

# 获取长度
print(len(s))  # 14

# 索引（从0开始）
print(s[0])    # H
print(s[-1])   # !（负数从后往前）

# 切片
print(s[0:5])  # Hello
print(s[7:])   # Python!
print(s[:5])   # Hello

# 字符串方法
print(s.upper())      # HELLO, PYTHON!
print(s.lower())      # hello, python!
print(s.replace("Python", "World"))  # Hello, World!

# 字符串拼接
first = "Hello"
second = "World"
result = first + " " + second
print(result)  # Hello World

# 字符串重复
print("=" * 20)
```

### 8.4 布尔值 (bool)

布尔值只有两个：`True`（真）和 `False`（假）。

```python
is_student = True
is_teacher = False

print(is_student, type(is_student))  # True <class 'bool'>
print(is_teacher, type(is_teacher))
```

**比较运算产生布尔值：**

```python
print(5 > 3)   # True
print(5 < 3)   # False
print(5 == 5)  # True
print(5 != 5)
```

**布尔值与其他类型的转换：**

```python
# 数字转布尔
print(bool(0))     # False（0 为假）
print(bool(1))     # True（非0 为真）
print(bool(-1))    # True
print(bool(3.14))  # True

# 字符串转布尔
print(bool(""))      # False（空字符串为假）
print(bool("hello")) # True（非空字符串为真）

# 布尔转数字
print(int(True))   # 1
print(int(False))
```

---

## 9. 类型转换

Python 提供了内置函数进行类型转换。

### 9.1 常用转换函数

| 函数 | 说明 | 示例 |
|------|------|------|
| `int(x)` | 转换为整数 | `int("123")` → `123` |
| `float(x)` | 转换为浮点数 | `float("3.14")` → `3.14` |
| `str(x)` | 转换为字符串 | `str(100)` → `"100"` |
| `bool(x)` | 转换为布尔值 | `bool(1)` → `True` |

### 9.2 转换示例

```python
# 字符串转数字
num_str = "123"
num_int = int(num_str)
print(num_int + 1)  # 124

num_str2 = "3.14"
num_float = float(num_str2)
print(num_float * 2)  # 6.28

# 数字转字符串
age = 18
age_str = str(age)
print("年龄：" + age_str)  # 年龄：18

# 浮点数转整数（截断小数部分）
pi = 3.99
print(int(pi))  # 3（不是四舍五入！）

# 整数转浮点数
num = 10
print(float(num))
```

### 9.3 转换注意事项

```python
# 注意：不能将非数字字符串转为数字
# int("abc")  # ValueError: invalid literal for int()

# 注意：有小数点的字符串不能直接转int
# int("3.14")  # ValueError

# 正确做法：先转float再转int
print(int(float("3.14")))  # 3
```

---

## 10. 运算符

### 10.1 算术运算符

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `+` | 加法 | `5 + 3` → `8` |
| `-` | 减法 | `5 - 3` → `2` |
| `*` | 乘法 | `5 * 3` → `15` |
| `/` | 除法（结果为浮点数） | `5 / 2` → `2.5` |
| `//` | 整除（向下取整） | `5 // 2` → `2` |
| `%` | 取余（模运算） | `5 % 2` → `1` |
| `**` | 幂运算 | `2 ** 3` → `8` |

```python
a = 10
b = 3

print(f"{a} + {b} = {a + b}")   # 10 + 3 = 13
print(f"{a} - {b} = {a - b}")   # 10 - 3 = 7
print(f"{a} * {b} = {a * b}")   # 10 * 3 = 30
print(f"{a} / {b} = {a / b}")   # 10 / 3 = 3.3333...
print(f"{a} // {b} = {a // b}") # 10 // 3 = 3
print(f"{a} % {b} = {a % b}")   # 10 % 3 = 1
print(f"{a} ** {b} = {a ** b}")
```

### 10.2 比较运算符

比较运算符返回布尔值 `True` 或 `False`。

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `==` | 等于 | `5 == 5` → `True` |
| `!=` | 不等于 | `5 != 3` → `True` |
| `>` | 大于 | `5 > 3` → `True` |
| `<` | 小于 | `5 < 3` → `False` |
| `>=` | 大于等于 | `5 >= 5` → `True` |
| `<=` | 小于等于 | `5 <= 3` → `False` |

```python
x = 5
y = 3

print(f"{x} == {y}: {x == y}")  # False
print(f"{x} != {y}: {x != y}")  # True
print(f"{x} > {y}: {x > y}")    # True
print(f"{x} < {y}: {x < y}")    # False
print(f"{x} >= {y}: {x >= y}")  # True
print(f"{x} <= {y}: {x <= y}")
```

### 10.3 赋值运算符

| 运算符 | 说明 | 等价于 |
|--------|------|--------|
| `=` | 赋值 | - |
| `+=` | 加后赋值 | `x = x + y` |
| `-=` | 减后赋值 | `x = x - y` |
| `*=` | 乘后赋值 | `x = x * y` |
| `/=` | 除后赋值 | `x = x / y` |
| `//=` | 整除后赋值 | `x = x // y` |
| `%=` | 取余后赋值 | `x = x % y` |
| `**=` | 幂后赋值 | `x = x ** y` |

```python
x = 10
print(f"初始值: x = {x}")  # 10

x += 5   # x = x + 5
print(f"x += 5: x = {x}")  # 15

x -= 3   # x = x - 3
print(f"x -= 3: x = {x}")  # 12

x *= 2   # x = x * 2
print(f"x *= 2: x = {x}")  # 24

x //= 5  # x = x // 5
print(f"x //= 5: x = {x}")
```

### 10.4 逻辑运算符

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `and` | 与（两个都为真才为真） | `True and False` → `False` |
| `or` | 或（有一个为真就为真） | `True or False` → `True` |
| `not` | 非（取反） | `not True` → `False` |

```python
a = True
b = False

print(f"True and False = {a and b}")  # False
print(f"True or False = {a or b}")    # True
print(f"not True = {not a}")          # False
print(f"not False = {not b}")         # True

# 实际应用
age = 20
has_id = True

if age >= 18 and has_id:
    print("允许进入")
else:
    print("禁止进入")
```

### 10.5 运算符优先级

从高到低的优先级：

1. `**` 幂运算
2. `*`, `/`, `//`, `%` 乘、除、整除、取余
3. `+`, `-` 加、减
4. `==`, `!=`, `>`, `<`, `>=`, `<=` 比较
5. `not` 逻辑非
6. `and` 逻辑与
7. `or` 逻辑或

```python
# 优先级示例
print(2 + 3 * 4)      # 14（先乘后加）
print((2 + 3) * 4)    # 20（括号优先）
print(2 ** 3 * 2)     # 16（先幂运算）
print(True or False and False)
```

---

## 11. 输入和输出

### 11.1 print() 输出

`print()` 函数用于在屏幕上输出内容。

**基本用法：**

```python
# 输出字符串
print("Hello, World!")

# 输出变量
name = "张三"
print(name)

# 输出多个值（默认用空格分隔）
print("姓名:", name, "年龄:", 18)
```

**参数详解：**

```python
# sep 参数：设置分隔符（默认为空格）
print("2024", "01", "15", sep="-")  # 2024-01-15
print("a", "b", "c", sep="")        # abc
print("a", "b", "c", sep=", ")      # a, b, c

# end 参数：设置结尾（默认为换行符）
print("Hello", end=" ")
print("World")  # Hello World（在同一行）

print("第一行", end="\n\n")
print("第三行")
```

### 11.2 格式化输出

**方法一：f-string（推荐）**

```python
name = "张三"
age = 18
score = 95.5

# 基本用法
print(f"姓名：{name}，年龄：{age}")

# 表达式
print(f"明年 {age + 1} 岁")

# 格式控制
print(f"成绩：{score:.1f}")  # 保留1位小数
print(f"成绩：{score:>10}")  # 右对齐，宽度10
print(f"编号：{1:03d}")
```

**方法二：format() 方法**

```python
name = "张三"
age = 18

# 位置参数
print("姓名：{}，年龄：{}".format(name, age))

# 索引参数
print("{0} 今年 {1} 岁，{0} 是学生".format(name, age))

# 关键字参数
print("姓名：{n}，年龄：{a}".format(n=name, a=age))
```

**方法三：% 格式化（旧式）**

```python
name = "张三"
age = 18
score = 95.5

print("姓名：%s，年龄：%d" % (name, age))
print("成绩：%.2f" % score)
```

### 11.3 input() 输入

`input()` 函数用于获取用户输入。

**基本用法：**

```python
# 获取用户输入
name = input("请输入你的名字：")
print(f"你好，{name}！")
```

> **注意**：`input()` 返回的**始终是字符串**类型！

```python
# input() 返回字符串
age_str = input("请输入年龄：")
print(type(age_str))  # <class 'str'>

# 需要转换类型才能进行数学运算
age = int(age_str)
print(f"明年你 {age + 1} 岁")

# 简写形式
age = int(input("请输入年龄："))
print(f"明年你 {age + 1} 岁")
```

---

## 12. 常见错误与调试

### 12.1 SyntaxError 语法错误

语法错误是代码不符合 Python 语法规则。

```python
# 错误1：缺少冒号
# if True
#     print("Hello")

# 正确：
if True:
    print("Hello")

# 错误2：缩进错误
# if True:
# print("Hello")  # IndentationError

# 正确：
if True:
    print("Hello")

# 错误3：引号不匹配
# print("Hello')

# 正确：
print("Hello")
```

### 12.2 NameError 名称错误

使用了未定义的变量。

```python
# 错误：变量名拼写错误
student_name = "张三"
# print(studnet_name)  # NameError: name 'studnet_name' is not defined

# 正确：
print(student_name)
```

### 12.3 TypeError 类型错误

操作的数据类型不正确。

```python
# 错误：字符串和数字不能直接相加
age = 18
# print("年龄：" + age)  # TypeError

# 正确方法1：转换类型
print("年龄：" + str(age))

# 正确方法2：使用 f-string
print(f"年龄：{age}")

# 正确方法3：使用逗号分隔
print("年龄：", age)
```

### 12.4 ValueError 值错误

值的类型正确但内容不合适。

```python
# 错误：不能将非数字字符串转为整数
# num = int("abc")  # ValueError: invalid literal for int()

# 正确：
num = int("123")
print(num)  # 123
```

### 12.5 调试技巧

1. **使用 print() 输出变量值**
2. **检查变量类型**：`print(type(变量))`
3. **仔细阅读错误信息**：错误信息会告诉你出错的行号和原因
4. **使用代码编辑器的语法检查功能**

```python
# 调试示例
def debug_example():
    x = "100"
    print(f"x 的值是：{x}")
    print(f"x 的类型是：{type(x)}")

    # 发现问题：x 是字符串，需要转换
    x = int(x)
    print(f"转换后 x 的类型是：{type(x)}")
    print(f"x + 1 = {x + 1}")

debug_example()
```

---

## 13. 小结

本章学习了 Python 的基础知识：

| 知识点 | 内容 |
|--------|------|
| 编码与标识符 | UTF-8 编码、命名规则、保留字 |
| 注释 | 单行 `#`、多行 `'''` 或 `"""` |
| 缩进 | 使用缩进表示代码块 |
| 变量 | 创建、赋值、命名规范 |
| 数据类型 | `int`、`float`、`str`、`bool` |
| 类型转换 | `int()`、`float()`、`str()`、`bool()` |
| 运算符 | 算术、比较、赋值、逻辑 |
| 输入输出 | `print()`、`input()` |

---

## 14. 练习

1. **计算圆的面积**：输入半径，计算并输出圆的面积（π 取 3.14159）
2. **温度转换**：输入摄氏温度，转换为华氏温度（公式：F = C × 9/5 + 32）
3. **交换变量**：定义两个变量 a=10, b=20，交换它们的值并输出

**提示**：到"代码练习场"尝试编写这些程序！
