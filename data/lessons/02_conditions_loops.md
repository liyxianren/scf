# 条件分支与循环

程序不仅仅是顺序执行，还需要根据条件做出决策，以及重复执行某些操作。本章将学习条件语句和循环结构。

## 1. 条件语句

### 1.1 if 语句

最简单的条件判断：

```python
age = 18

if age >= 18:
    print("你已成年")
```

> **重要**：Python使用缩进（通常是4个空格）来表示代码块，而不是花括号。

### 1.2 if-else 语句

二选一的情况：

```python
score = 75

if score >= 60:
    print("及格了！")
else:
    print("需要努力！")
```

### 1.3 if-elif-else 语句

多个条件判断：

```python
score = 85

if score >= 90:
    grade = "优秀"
elif score >= 80:
    grade = "良好"
elif score >= 70:
    grade = "中等"
elif score >= 60:
    grade = "及格"
else:
    grade = "不及格"

print(f"成绩等级：{grade}")  # 成绩等级：良好
```

### 1.4 比较运算符

| 运算符 | 含义 | 示例 |
|--------|------|------|
| == | 等于 | `5 == 5` → True |
| != | 不等于 | `5 != 3` → True |
| > | 大于 | `5 > 3` → True |
| < | 小于 | `3 < 5` → True |
| >= | 大于等于 | `5 >= 5` → True |
| <= | 小于等于 | `3 <= 5` → True |

### 1.5 逻辑运算符

| 运算符 | 含义 | 示例 |
|--------|------|------|
| and | 与（两个都为真才为真） | `True and True` → True |
| or | 或（有一个为真就为真） | `True or False` → True |
| not | 非（取反） | `not True` → False |

```python
age = 25
has_id = True

# 使用 and
if age >= 18 and has_id:
    print("可以进入")

# 使用 or
is_vip = False
if age >= 60 or is_vip:
    print("可以优先")

# 使用 not
is_banned = False
if not is_banned:
    print("账号正常")
```

### 1.6 条件表达式（三元运算符）

简洁的写法：

```python
age = 20

# 传统写法
if age >= 18:
    status = "成年"
else:
    status = "未成年"

# 条件表达式
status = "成年" if age >= 18 else "未成年"
print(status)  # 成年
```

## 2. for 循环

当你知道要重复多少次时，使用 for 循环。

### 2.1 遍历序列

```python
# 遍历字符串
for char in "Python":
    print(char)

# 遍历列表
fruits = ["苹果", "香蕉", "橙子"]
for fruit in fruits:
    print(f"我喜欢{fruit}")
```

### 2.2 range() 函数

生成数字序列：

```python
# range(5) 生成 0, 1, 2, 3, 4
for i in range(5):
    print(i)

# range(1, 6) 生成 1, 2, 3, 4, 5
for i in range(1, 6):
    print(i)

# range(0, 10, 2) 生成 0, 2, 4, 6, 8（步长为2）
for i in range(0, 10, 2):
    print(i)

# 倒序 range(5, 0, -1) 生成 5, 4, 3, 2, 1
for i in range(5, 0, -1):
    print(i)
```

### 2.3 实用示例

```python
# 计算1到100的和
total = 0
for i in range(1, 101):
    total += i
print(f"1到100的和是：{total}")  # 5050

# 九九乘法表
for i in range(1, 10):
    for j in range(1, i + 1):
        print(f"{j}×{i}={i*j}", end="\t")
    print()  # 换行
```

### 2.4 enumerate() 获取索引

```python
fruits = ["苹果", "香蕉", "橙子"]

for index, fruit in enumerate(fruits):
    print(f"{index}: {fruit}")

# 输出：
# 0: 苹果
# 1: 香蕉
# 2: 橙子
```

## 3. while 循环

当不确定循环次数，根据条件决定是否继续时，使用 while 循环。

### 3.1 基本语法

```python
count = 0

while count < 5:
    print(f"当前计数：{count}")
    count += 1  # 不要忘记更新条件，否则会死循环！

print("循环结束")
```

### 3.2 用户输入验证

```python
# 密码验证示例
correct_password = "123456"

while True:
    password = input("请输入密码：")
    if password == correct_password:
        print("密码正确，登录成功！")
        break  # 退出循环
    else:
        print("密码错误，请重试")
```

### 3.3 猜数字游戏

```python
import random

secret = random.randint(1, 100)
attempts = 0

print("我想了一个1到100之间的数字，猜猜看！")

while True:
    guess = int(input("你的猜测："))
    attempts += 1

    if guess < secret:
        print("太小了！")
    elif guess > secret:
        print("太大了！")
    else:
        print(f"恭喜你猜对了！用了{attempts}次")
        break
```

## 4. 循环控制语句

### 4.1 break - 立即退出循环

```python
# 找到第一个能被7整除的数
for i in range(1, 100):
    if i % 7 == 0:
        print(f"找到了：{i}")
        break  # 找到后立即退出

# 输出：找到了：7
```

### 4.2 continue - 跳过本次，继续下一次

```python
# 打印1到10中的奇数
for i in range(1, 11):
    if i % 2 == 0:  # 如果是偶数
        continue    # 跳过
    print(i)

# 输出：1 3 5 7 9
```

### 4.3 else 子句

循环正常结束（没有被break）时执行：

```python
# 判断是否为质数
n = 17

for i in range(2, n):
    if n % i == 0:
        print(f"{n}不是质数，可以被{i}整除")
        break
else:
    print(f"{n}是质数")

# 输出：17是质数
```

## 5. 嵌套循环

循环中可以包含另一个循环：

```python
# 打印矩形
rows = 3
cols = 5

for i in range(rows):
    for j in range(cols):
        print("*", end="")
    print()  # 换行

# 输出：
# *****
# *****
# *****

# 打印直角三角形
for i in range(1, 6):
    print("*" * i)

# 输出：
# *
# **
# ***
# ****
# *****
```

## 6. 常见错误与调试

### 错误1：缩进错误

```python
if True:
print("Hello")  # IndentationError: expected an indented block

# 正确做法
if True:
    print("Hello")
```

### 错误2：无限循环

```python
# 错误：忘记更新计数器
count = 0
while count < 5:
    print(count)
    # 缺少 count += 1，导致死循环

# 正确做法
count = 0
while count < 5:
    print(count)
    count += 1
```

### 错误3：range边界

```python
# 注意：range(1, 5) 不包含5
for i in range(1, 5):
    print(i)  # 输出 1, 2, 3, 4

# 如果想包含5
for i in range(1, 6):
    print(i)  # 输出 1, 2, 3, 4, 5
```

### 错误4：比较运算符写错

```python
x = 5

# 错误：用了赋值运算符
if x = 5:  # SyntaxError
    print("等于5")

# 正确：用比较运算符
if x == 5:
    print("等于5")
```

## 小结

本章学习了：
- 条件语句：if、if-else、if-elif-else
- 比较运算符和逻辑运算符
- for循环和range()函数
- while循环
- break、continue控制语句
- 嵌套循环

**练习建议**：
1. 编写一个程序判断一个数是正数、负数还是零
2. 使用for循环计算1到N的阶乘
3. 编写一个简单的猜数字游戏
