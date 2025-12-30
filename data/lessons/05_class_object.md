# 类与对象

面向对象编程（OOP）是一种编程范式，Python完全支持面向对象编程。本章将介绍类和对象的基本概念。

## 1. 什么是类和对象？

### 1.1 概念理解

- **类（Class）**：是对象的蓝图或模板，定义了对象的属性和行为
- **对象（Object）**：是类的实例，是根据类创建的具体事物

**生活中的例子**：
- 类就像"汽车设计图"，定义了汽车应该有什么（轮子、引擎、颜色等）
- 对象就像"你的那辆具体的车"，是根据设计图制造出来的

```python
# 类 = 设计图
# 对象 = 根据设计图造出来的实物

# 学生类 -> 张三（对象）、李四（对象）
# 汽车类 -> 我的宝马（对象）、你的奔驰（对象）
```

## 2. 定义类

### 2.1 最简单的类

```python
class Student:
    pass  # 空类

# 创建对象（实例化）
student1 = Student()
student2 = Student()

print(type(student1))  # <class '__main__.Student'>
print(student1)        # <__main__.Student object at 0x...>
```

### 2.2 带属性的类

```python
class Student:
    # 类属性（所有实例共享）
    school = "Python学校"

# 创建对象
s1 = Student()
s2 = Student()

# 访问类属性
print(s1.school)  # Python学校
print(s2.school)  # Python学校

# 给对象添加实例属性
s1.name = "张三"
s1.age = 18

print(s1.name)  # 张三
print(s1.age)   # 18
```

## 3. 构造函数 __init__

`__init__` 是特殊方法，在创建对象时自动调用，用于初始化对象的属性。

```python
class Student:
    def __init__(self, name, age):
        """构造函数"""
        self.name = name  # 实例属性
        self.age = age    # 实例属性

# 创建对象时传入参数
s1 = Student("张三", 18)
s2 = Student("李四", 17)

print(s1.name, s1.age)  # 张三 18
print(s2.name, s2.age)  # 李四 17
```

### 3.1 带默认值的构造函数

```python
class Student:
    def __init__(self, name, age=18, grade="高三"):
        self.name = name
        self.age = age
        self.grade = grade

s1 = Student("张三")           # 使用默认值
s2 = Student("李四", 17)        # 部分使用默认值
s3 = Student("王五", 16, "高二")  # 全部指定

print(f"{s1.name}, {s1.age}, {s1.grade}")  # 张三, 18, 高三
print(f"{s2.name}, {s2.age}, {s2.grade}")  # 李四, 17, 高三
print(f"{s3.name}, {s3.age}, {s3.grade}")  # 王五, 16, 高二
```

## 4. 实例方法

方法是定义在类中的函数，用于描述对象的行为。

```python
class Student:
    def __init__(self, name, age):
        self.name = name
        self.age = age
        self.scores = []

    def introduce(self):
        """自我介绍方法"""
        print(f"大家好，我叫{self.name}，今年{self.age}岁")

    def add_score(self, score):
        """添加成绩"""
        self.scores.append(score)

    def get_average(self):
        """计算平均分"""
        if len(self.scores) == 0:
            return 0
        return sum(self.scores) / len(self.scores)

# 使用方法
student = Student("张三", 18)
student.introduce()        # 大家好，我叫张三，今年18岁

student.add_score(85)
student.add_score(90)
student.add_score(88)

print(f"平均分：{student.get_average():.1f}")  # 平均分：87.7
```

### 4.1 self 参数

`self` 代表对象本身，通过它可以访问对象的属性和方法。

```python
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1  # 通过self访问实例属性

    def decrement(self):
        self.count -= 1

    def reset(self):
        self.count = 0

    def get_count(self):
        return self.count

counter = Counter()
counter.increment()
counter.increment()
counter.increment()
print(counter.get_count())  # 3

counter.decrement()
print(counter.get_count())  # 2
```

## 5. 实例属性 vs 类属性

```python
class Dog:
    # 类属性：所有Dog对象共享
    species = "犬科"
    dog_count = 0

    def __init__(self, name, age):
        # 实例属性：每个对象独有
        self.name = name
        self.age = age
        Dog.dog_count += 1  # 修改类属性

# 类属性通过类名访问
print(Dog.species)     # 犬科
print(Dog.dog_count)   # 0

# 创建对象
dog1 = Dog("旺财", 3)
dog2 = Dog("小白", 2)

# 实例属性通过对象访问
print(dog1.name)       # 旺财
print(dog2.name)       # 小白

# 类属性被所有实例共享
print(Dog.dog_count)   # 2
print(dog1.dog_count)  # 2
print(dog2.dog_count)  # 2
```

### 5.1 修改属性的注意事项

```python
class MyClass:
    class_attr = "类属性"

obj = MyClass()

# 通过对象访问类属性
print(obj.class_attr)  # 类属性

# 通过对象"修改"类属性，实际上是创建了同名的实例属性
obj.class_attr = "实例属性"
print(obj.class_attr)      # 实例属性（实例属性）
print(MyClass.class_attr)  # 类属性（类属性没变）

# 要修改类属性，必须通过类名
MyClass.class_attr = "修改后的类属性"
print(MyClass.class_attr)  # 修改后的类属性
```

## 6. 完整示例：银行账户类

```python
class BankAccount:
    """银行账户类"""

    # 类属性
    bank_name = "Python银行"
    interest_rate = 0.02  # 年利率

    def __init__(self, owner, balance=0):
        """初始化账户"""
        self.owner = owner
        self.balance = balance
        self.transactions = []

    def deposit(self, amount):
        """存款"""
        if amount > 0:
            self.balance += amount
            self.transactions.append(f"存款: +{amount}")
            print(f"存款成功！当前余额：{self.balance}")
        else:
            print("存款金额必须大于0")

    def withdraw(self, amount):
        """取款"""
        if amount <= 0:
            print("取款金额必须大于0")
        elif amount > self.balance:
            print("余额不足！")
        else:
            self.balance -= amount
            self.transactions.append(f"取款: -{amount}")
            print(f"取款成功！当前余额：{self.balance}")

    def get_balance(self):
        """查询余额"""
        return self.balance

    def show_transactions(self):
        """显示交易记录"""
        print(f"--- {self.owner}的交易记录 ---")
        for t in self.transactions:
            print(t)

    def add_interest(self):
        """计算利息"""
        interest = self.balance * BankAccount.interest_rate
        self.balance += interest
        self.transactions.append(f"利息: +{interest:.2f}")
        print(f"利息已到账：{interest:.2f}")


# 使用示例
account = BankAccount("张三", 1000)
print(f"银行：{BankAccount.bank_name}")
print(f"账户持有人：{account.owner}")
print(f"初始余额：{account.get_balance()}")

account.deposit(500)
account.withdraw(200)
account.add_interest()

account.show_transactions()
```

## 7. 方法类型

### 7.1 实例方法

最常用的方法，第一个参数是 `self`：

```python
class MyClass:
    def instance_method(self):
        print(f"实例方法，self = {self}")
```

### 7.2 类方法

使用 `@classmethod` 装饰器，第一个参数是 `cls`：

```python
class Student:
    count = 0

    def __init__(self, name):
        self.name = name
        Student.count += 1

    @classmethod
    def get_count(cls):
        """类方法，返回学生数量"""
        return cls.count

    @classmethod
    def create_anonymous(cls):
        """类方法，创建匿名学生"""
        return cls("匿名")

# 使用类方法
print(Student.get_count())  # 0

s1 = Student("张三")
s2 = Student("李四")
print(Student.get_count())  # 2

s3 = Student.create_anonymous()
print(s3.name)  # 匿名
```

### 7.3 静态方法

使用 `@staticmethod` 装饰器，不需要特殊参数：

```python
class MathUtils:
    @staticmethod
    def add(a, b):
        return a + b

    @staticmethod
    def is_even(n):
        return n % 2 == 0

# 使用静态方法
print(MathUtils.add(3, 5))      # 8
print(MathUtils.is_even(4))     # True
```

## 8. 常见错误与调试

### 错误1：忘记 self

```python
class Student:
    def __init__(name, age):  # 错误：缺少self
        name = name
        age = age

# TypeError: __init__() takes 2 positional arguments but 3 were given

# 正确：
class Student:
    def __init__(self, name, age):
        self.name = name
        self.age = age
```

### 错误2：忘记 self.

```python
class Student:
    def __init__(self, name):
        name = name  # 错误：没有使用self.，只是局部变量

    def greet(self):
        print(name)  # NameError: name 'name' is not defined

# 正确：
class Student:
    def __init__(self, name):
        self.name = name  # 存储为实例属性

    def greet(self):
        print(self.name)  # 通过self访问
```

### 错误3：直接修改类属性

```python
class Counter:
    count = 0

    def __init__(self):
        self.count += 1  # 这会创建实例属性，而不是修改类属性

# 正确：
class Counter:
    count = 0

    def __init__(self):
        Counter.count += 1  # 通过类名修改
```

## 9. 私有属性和方法

Python使用命名约定来表示私有成员：

```python
class Person:
    def __init__(self, name, age):
        self.name = name      # 公开属性
        self._phone = ""      # 约定：内部使用（单下划线）
        self.__password = ""  # 名称改写（双下划线）

    def set_password(self, pwd):
        self.__password = pwd

    def check_password(self, pwd):
        return self.__password == pwd

person = Person("张三", 18)
print(person.name)       # 张三（可以访问）
print(person._phone)     # ""（可以访问，但不建议）
# print(person.__password)  # AttributeError

# 名称改写：__password 变成 _Person__password
print(person._Person__password)  # ""（可以访问，但强烈不建议）

# 正确使用方式
person.set_password("123456")
print(person.check_password("123456"))  # True
```

## 小结

本章学习了：
- 类和对象的概念
- 使用 `class` 关键字定义类
- 构造函数 `__init__` 的使用
- 实例属性和类属性的区别
- 实例方法、类方法、静态方法
- `self` 参数的作用
- 私有属性和方法的约定

**练习建议**：
1. 创建一个 `Rectangle` 类，包含长和宽，能计算面积和周长
2. 创建一个 `Book` 类，包含书名、作者、价格，能显示书籍信息
3. 创建一个 `ShoppingCart` 类，能添加商品、删除商品、计算总价
