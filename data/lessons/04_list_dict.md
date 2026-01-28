# 列表与字典

列表和字典是Python中最常用的数据结构，用于存储和组织数据。

## 1. 列表 (List)

列表是有序的元素集合，可以存储不同类型的数据。

### 1.1 创建列表

```python
# 创建空列表
empty_list = []
empty_list2 = list()

# 创建有元素的列表
numbers = [1, 2, 3, 4, 5]
names = ["张三", "李四", "王五"]
mixed = [1, "hello", 3.14, True]

print(numbers)  # [1, 2, 3, 4, 5]
```

### 1.2 访问元素（索引）

```python
fruits = ["苹果", "香蕉", "橙子", "葡萄", "西瓜"]

# 正向索引（从0开始）
print(fruits[0])   # 苹果
print(fruits[2])   # 橙子

# 负向索引（从后往前）
print(fruits[-1])  # 西瓜（最后一个）
print(fruits[-2])  # 葡萄（倒数第二个）
```

### 1.3 切片操作

```python
numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# [起始:结束]（不包含结束位置）
print(numbers[2:5])   # [2, 3, 4]
print(numbers[:3])    # [0, 1, 2]（从头开始）
print(numbers[7:])    # [7, 8, 9]（到末尾）
print(numbers[-3:])   # [7, 8, 9]（最后3个）

# [起始:结束:步长]
print(numbers[::2])   # [0, 2, 4, 6, 8]（每隔一个）
print(numbers[1::2])  # [1, 3, 5, 7, 9]（奇数位置）
print(numbers[::-1])  # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]（反转）
```

### 1.4 修改列表

```python
fruits = ["苹果", "香蕉", "橙子"]

# 修改元素
fruits[1] = "草莓"
print(fruits)  # ['苹果', '草莓', '橙子']

# 添加元素
fruits.append("葡萄")       # 末尾添加
print(fruits)  # ['苹果', '草莓', '橙子', '葡萄']

fruits.insert(1, "芒果")    # 指定位置插入
print(fruits)  # ['苹果', '芒果', '草莓', '橙子', '葡萄']

# 合并列表
fruits.extend(["西瓜", "桃子"])
print(fruits)

# 也可以用 +
new_fruits = ["苹果"] + ["香蕉", "橙子"]
print(new_fruits)  # ['苹果', '香蕉', '橙子']
```

### 1.5 删除元素

```python
fruits = ["苹果", "香蕉", "橙子", "香蕉", "葡萄"]

# 按值删除（只删第一个匹配的）
fruits.remove("香蕉")
print(fruits)  # ['苹果', '橙子', '香蕉', '葡萄']

# 按索引删除
del fruits[1]
print(fruits)  # ['苹果', '香蕉', '葡萄']

# pop() 删除并返回元素
last = fruits.pop()     # 删除最后一个
print(last)             # 葡萄
first = fruits.pop(0)   # 删除第一个
print(first)            # 苹果

# 清空列表
fruits.clear()
print(fruits)  # []
```

### 1.6 常用列表方法

```python
numbers = [3, 1, 4, 1, 5, 9, 2, 6]

# 获取长度
print(len(numbers))  # 8

# 计数
print(numbers.count(1))  # 2（1出现了2次）

# 查找索引
print(numbers.index(5))  # 4（5在索引4位置）

# 排序
numbers.sort()           # 升序排序（修改原列表）
print(numbers)           # [1, 1, 2, 3, 4, 5, 6, 9]

numbers.sort(reverse=True)  # 降序排序
print(numbers)              # [9, 6, 5, 4, 3, 2, 1, 1]

# 不修改原列表的排序
original = [3, 1, 4, 1, 5]
sorted_list = sorted(original)
print(original)     # [3, 1, 4, 1, 5]（不变）
print(sorted_list)  # [1, 1, 3, 4, 5]

# 反转
numbers.reverse()
print(numbers)

# 复制列表
copy1 = numbers.copy()
copy2 = numbers[:]
copy3 = list(numbers)
```

### 1.7 列表推导式

简洁地创建列表：

```python
# 传统方式
squares = []
for i in range(1, 6):
    squares.append(i ** 2)
print(squares)  # [1, 4, 9, 16, 25]

# 列表推导式
squares = [i ** 2 for i in range(1, 6)]
print(squares)  # [1, 4, 9, 16, 25]

# 带条件的列表推导式
evens = [i for i in range(10) if i % 2 == 0]
print(evens)  # [0, 2, 4, 6, 8]

# 更复杂的例子
words = ["hello", "world", "python"]
upper_words = [word.upper() for word in words]
print(upper_words)  # ['HELLO', 'WORLD', 'PYTHON']

# 嵌套列表推导式
matrix = [[i * j for j in range(1, 4)] for i in range(1, 4)]
print(matrix)  # [[1, 2, 3], [2, 4, 6], [3, 6, 9]]
```

## 2. 字典 (Dictionary)

字典是键值对的集合，用于存储关联数据。

### 2.1 创建字典

```python
# 创建空字典
empty_dict = {}
empty_dict2 = dict()

# 创建有元素的字典
student = {
    "name": "张三",
    "age": 18,
    "grade": "高三"
}

# 另一种方式
student2 = dict(name="李四", age=17, grade="高二")

print(student)
```

### 2.2 访问元素

```python
student = {"name": "张三", "age": 18, "grade": "高三"}

# 使用键访问
print(student["name"])  # 张三
print(student["age"])   # 18

# 使用get()方法（更安全）
print(student.get("name"))      # 张三
print(student.get("score"))     # None（键不存在）
print(student.get("score", 0))  # 0（设置默认值）

# 直接访问不存在的键会报错
# print(student["score"])  # KeyError
```

### 2.3 修改字典

```python
student = {"name": "张三", "age": 18}

# 修改值
student["age"] = 19
print(student)  # {'name': '张三', 'age': 19}

# 添加新键值对
student["grade"] = "高三"
student["score"] = 95
print(student)

# 批量更新
student.update({"age": 20, "city": "北京"})
print(student)
```

### 2.4 删除元素

```python
student = {"name": "张三", "age": 18, "grade": "高三"}

# del删除
del student["grade"]
print(student)  # {'name': '张三', 'age': 18}

# pop()删除并返回值
age = student.pop("age")
print(age)      # 18
print(student)  # {'name': '张三'}

# pop()带默认值
score = student.pop("score", 0)  # 键不存在返回默认值
print(score)  # 0

# 清空字典
student.clear()
print(student)  # {}
```

### 2.5 遍历字典

```python
student = {"name": "张三", "age": 18, "grade": "高三"}

# 遍历键
for key in student:
    print(key)

# 遍历键（显式）
for key in student.keys():
    print(key)

# 遍历值
for value in student.values():
    print(value)

# 遍历键值对
for key, value in student.items():
    print(f"{key}: {value}")
```

### 2.6 常用字典方法

```python
student = {"name": "张三", "age": 18}

# 获取所有键
print(student.keys())    # dict_keys(['name', 'age'])

# 获取所有值
print(student.values())  # dict_values(['张三', 18])

# 获取所有键值对
print(student.items())   # dict_items([('name', '张三'), ('age', 18)])

# 检查键是否存在
print("name" in student)   # True
print("score" in student)  # False

# 获取长度
print(len(student))  # 2

# 复制字典
copy_student = student.copy()
```

### 2.7 字典推导式

```python
# 基本用法
squares = {x: x**2 for x in range(1, 6)}
print(squares)  # {1: 1, 2: 4, 3: 9, 4: 16, 5: 25}

# 带条件
evens = {x: x**2 for x in range(10) if x % 2 == 0}
print(evens)  # {0: 0, 2: 4, 4: 16, 6: 36, 8: 64}

# 转换列表为字典
names = ["张三", "李四", "王五"]
name_lengths = {name: len(name) for name in names}
print(name_lengths)  # {'张三': 2, '李四': 2, '王五': 2}

# 交换键值
original = {"a": 1, "b": 2, "c": 3}
swapped = {v: k for k, v in original.items()}
print(swapped)  # {1: 'a', 2: 'b', 3: 'c'}
```

## 3. 嵌套结构

### 3.1 嵌套列表

```python
# 二维列表（矩阵）
matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
]

print(matrix[0])      # [1, 2, 3]
print(matrix[1][2])   # 6

# 遍历二维列表
for row in matrix:
    for item in row:
        print(item, end=" ")
    print()
```

### 3.2 嵌套字典

```python
students = {
    "001": {"name": "张三", "age": 18, "scores": [85, 90, 88]},
    "002": {"name": "李四", "age": 17, "scores": [92, 88, 95]},
}

# 访问嵌套数据
print(students["001"]["name"])        # 张三
print(students["001"]["scores"][0])   # 85

# 遍历
for id, info in students.items():
    print(f"学号{id}: {info['name']}, 平均分: {sum(info['scores'])/len(info['scores']):.1f}")
```

### 3.3 字典列表

```python
students = [
    {"name": "张三", "score": 85},
    {"name": "李四", "score": 92},
    {"name": "王五", "score": 78}
]

# 按成绩排序
sorted_students = sorted(students, key=lambda s: s["score"], reverse=True)
for s in sorted_students:
    print(f"{s['name']}: {s['score']}")

# 找最高分
best = max(students, key=lambda s: s["score"])
print(f"最高分：{best['name']} - {best['score']}")
```

## 4. 实用技巧

### 4.1 列表解包

```python
a, b, c = [1, 2, 3]
print(a, b, c)  # 1 2 3

# 使用 * 收集剩余元素
first, *rest = [1, 2, 3, 4, 5]
print(first)  # 1
print(rest)   # [2, 3, 4, 5]

*front, last = [1, 2, 3, 4, 5]
print(front)  # [1, 2, 3, 4]
print(last)   # 5
```

### 4.2 zip 组合

```python
names = ["张三", "李四", "王五"]
scores = [85, 92, 78]

# 组合成字典
student_scores = dict(zip(names, scores))
print(student_scores)  # {'张三': 85, '李四': 92, '王五': 78}

# 组合成元组列表
combined = list(zip(names, scores))
print(combined)  # [('张三', 85), ('李四', 92), ('王五', 78)]
```

### 4.3 统计频率

```python
from collections import Counter

words = ["apple", "banana", "apple", "orange", "banana", "apple"]
counter = Counter(words)
print(counter)  # Counter({'apple': 3, 'banana': 2, 'orange': 1})
print(counter.most_common(2))  # [('apple', 3), ('banana', 2)]
```

## 5. 常见错误与调试

### 错误1：索引越界

```python
fruits = ["苹果", "香蕉", "橙子"]
# print(fruits[5])  # IndexError: list index out of range

# 安全访问
if len(fruits) > 5:
    print(fruits[5])
```

### 错误2：在遍历时修改列表

```python
numbers = [1, 2, 3, 4, 5]

# 错误做法
for num in numbers:
    if num % 2 == 0:
        numbers.remove(num)  # 可能跳过元素

# 正确做法1：创建新列表
numbers = [num for num in numbers if num % 2 != 0]

# 正确做法2：遍历副本
for num in numbers[:]:  # 遍历副本
    if num % 2 == 0:
        numbers.remove(num)
```

### 错误3：字典键不存在

```python
student = {"name": "张三"}
# print(student["age"])  # KeyError

# 使用get()
print(student.get("age", "未知"))  # 未知

# 或先检查
if "age" in student:
    print(student["age"])
```

## 小结

本章学习了：
- 列表的创建、索引、切片、修改、删除
- 常用列表方法：append, insert, remove, pop, sort, reverse等
- 列表推导式
- 字典的创建、访问、修改、删除
- 常用字典方法：keys, values, items, get, update等
- 字典推导式
- 嵌套结构：嵌套列表、嵌套字典

**练习建议**：
1. 创建一个学生成绩管理程序，使用字典存储学生信息
2. 实现一个购物车程序，使用列表存储商品
3. 统计一段文字中每个字符出现的次数
