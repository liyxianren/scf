# 面向对象编程

本章将深入学习面向对象编程的三大特性：封装、继承、多态，以及Python中的魔术方法。

## 1. 封装

封装是指将数据和操作数据的方法捆绑在一起，并对外隐藏内部实现细节。

### 1.1 封装的好处

```python
# 不使用封装（直接操作数据）
class Account:
    def __init__(self):
        self.balance = 0

acc = Account()
acc.balance = -1000  # 可以随意设置非法值

# 使用封装
class Account:
    def __init__(self):
        self._balance = 0  # 约定内部使用

    def deposit(self, amount):
        """存款方法"""
        if amount > 0:
            self._balance += amount
            return True
        return False

    def withdraw(self, amount):
        """取款方法"""
        if 0 < amount <= self._balance:
            self._balance -= amount
            return True
        return False

    def get_balance(self):
        """查询余额"""
        return self._balance

acc = Account()
acc.deposit(1000)
print(acc.get_balance())  # 1000
acc.withdraw(500)
print(acc.get_balance())  # 500
```

### 1.2 使用 property 装饰器

```python
class Circle:
    def __init__(self, radius):
        self._radius = radius

    @property
    def radius(self):
        """getter: 获取半径"""
        return self._radius

    @radius.setter
    def radius(self, value):
        """setter: 设置半径"""
        if value > 0:
            self._radius = value
        else:
            raise ValueError("半径必须大于0")

    @property
    def area(self):
        """只读属性：面积"""
        return 3.14159 * self._radius ** 2

# 使用
circle = Circle(5)
print(circle.radius)  # 5（像访问属性一样）
print(circle.area)    # 78.53975

circle.radius = 10    # 像设置属性一样
print(circle.area)    # 314.159

# circle.area = 100   # AttributeError: can't set attribute
# circle.radius = -5  # ValueError: 半径必须大于0
```

## 2. 继承

继承允许创建一个新类，继承另一个类的属性和方法。

### 2.1 基本继承

```python
# 父类（基类）
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        print(f"{self.name}发出声音")

    def eat(self):
        print(f"{self.name}在吃东西")

# 子类（派生类）
class Dog(Animal):
    def bark(self):
        print(f"{self.name}：汪汪汪！")

class Cat(Animal):
    def meow(self):
        print(f"{self.name}：喵喵喵！")

# 使用
dog = Dog("旺财")
dog.speak()  # 旺财发出声音（继承的方法）
dog.eat()    # 旺财在吃东西（继承的方法）
dog.bark()   # 旺财：汪汪汪！（自己的方法）

cat = Cat("小咪")
cat.speak()  # 小咪发出声音
cat.meow()   # 小咪：喵喵喵！
```

### 2.2 方法重写

子类可以重写父类的方法：

```python
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        print(f"{self.name}发出声音")

class Dog(Animal):
    def speak(self):  # 重写父类方法
        print(f"{self.name}：汪汪汪！")

class Cat(Animal):
    def speak(self):  # 重写父类方法
        print(f"{self.name}：喵喵喵！")

# 使用
animals = [Dog("旺财"), Cat("小咪"), Animal("未知")]

for animal in animals:
    animal.speak()
# 旺财：汪汪汪！
# 小咪：喵喵喵！
# 未知发出声音
```

### 2.3 super() 调用父类方法

```python
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def introduce(self):
        print(f"我是{self.name}，{self.age}岁")

class Student(Person):
    def __init__(self, name, age, student_id):
        super().__init__(name, age)  # 调用父类构造函数
        self.student_id = student_id

    def introduce(self):
        super().introduce()  # 调用父类方法
        print(f"我的学号是{self.student_id}")

student = Student("张三", 18, "2024001")
student.introduce()
# 我是张三，18岁
# 我的学号是2024001
```

### 2.4 isinstance() 和 issubclass()

```python
class Animal:
    pass

class Dog(Animal):
    pass

class Cat(Animal):
    pass

dog = Dog()

# 检查对象是否是某个类的实例
print(isinstance(dog, Dog))     # True
print(isinstance(dog, Animal))  # True（也是Animal的实例）
print(isinstance(dog, Cat))     # False

# 检查类是否是另一个类的子类
print(issubclass(Dog, Animal))  # True
print(issubclass(Cat, Animal))  # True
print(issubclass(Dog, Cat))     # False
```

### 2.5 多重继承

Python支持多重继承：

```python
class Flyable:
    def fly(self):
        print("我能飞！")

class Swimmable:
    def swim(self):
        print("我能游泳！")

class Duck(Flyable, Swimmable):
    def quack(self):
        print("嘎嘎嘎！")

duck = Duck()
duck.fly()    # 我能飞！
duck.swim()   # 我能游泳！
duck.quack()  # 嘎嘎嘎！
```

## 3. 多态

多态是指不同类的对象可以用相同的方式调用。

```python
class Shape:
    def area(self):
        pass

class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

class Circle(Shape):
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return 3.14159 * self.radius ** 2

class Triangle(Shape):
    def __init__(self, base, height):
        self.base = base
        self.height = height

    def area(self):
        return 0.5 * self.base * self.height

# 多态的使用
shapes = [
    Rectangle(4, 5),
    Circle(3),
    Triangle(6, 4)
]

for shape in shapes:
    print(f"面积：{shape.area():.2f}")
# 面积：20.00
# 面积：28.27
# 面积：12.00
```

## 4. 魔术方法

魔术方法（Magic Methods）是Python中以双下划线开头和结尾的特殊方法。

### 4.1 __str__ 和 __repr__

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        """用户友好的字符串表示"""
        return f"点({self.x}, {self.y})"

    def __repr__(self):
        """开发者友好的字符串表示"""
        return f"Point({self.x}, {self.y})"

p = Point(3, 4)
print(p)        # 点(3, 4) —— 调用 __str__
print(repr(p))  # Point(3, 4) —— 调用 __repr__
```

### 4.2 __len__ 和 __bool__

```python
class MyList:
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        return len(self.items) > 0

my_list = MyList([1, 2, 3])
print(len(my_list))  # 3

empty_list = MyList([])
if my_list:
    print("非空")   # 输出：非空
if not empty_list:
    print("空列表")  # 输出：空列表
```

### 4.3 比较运算符

```python
class Student:
    def __init__(self, name, score):
        self.name = name
        self.score = score

    def __eq__(self, other):
        """等于"""
        return self.score == other.score

    def __lt__(self, other):
        """小于"""
        return self.score < other.score

    def __le__(self, other):
        """小于等于"""
        return self.score <= other.score

    def __gt__(self, other):
        """大于"""
        return self.score > other.score

    def __str__(self):
        return f"{self.name}: {self.score}"

s1 = Student("张三", 85)
s2 = Student("李四", 90)
s3 = Student("王五", 85)

print(s1 < s2)   # True
print(s1 == s3)  # True
print(s2 > s1)   # True

# 可以排序
students = [s1, s2, s3]
sorted_students = sorted(students)
for s in sorted_students:
    print(s)
```

### 4.4 算术运算符

```python
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        """加法"""
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        """减法"""
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        """数乘"""
        return Vector(self.x * scalar, self.y * scalar)

    def __str__(self):
        return f"Vector({self.x}, {self.y})"

v1 = Vector(1, 2)
v2 = Vector(3, 4)

print(v1 + v2)   # Vector(4, 6)
print(v2 - v1)   # Vector(2, 2)
print(v1 * 3)    # Vector(3, 6)
```

### 4.5 索引和迭代

```python
class MyRange:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.data = list(range(start, end))

    def __getitem__(self, index):
        """索引访问"""
        return self.data[index]

    def __setitem__(self, index, value):
        """索引赋值"""
        self.data[index] = value

    def __iter__(self):
        """迭代器"""
        return iter(self.data)

    def __len__(self):
        return len(self.data)

r = MyRange(0, 5)
print(r[2])      # 2
r[2] = 100
print(r[2])      # 100

for item in r:
    print(item, end=" ")  # 0 1 100 3 4
```

### 4.6 上下文管理器

```python
class FileManager:
    def __init__(self, filename, mode):
        self.filename = filename
        self.mode = mode
        self.file = None

    def __enter__(self):
        """进入 with 块时调用"""
        self.file = open(self.filename, self.mode)
        return self.file

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出 with 块时调用"""
        if self.file:
            self.file.close()

# 使用
with FileManager("test.txt", "w") as f:
    f.write("Hello, World!")
# 文件会自动关闭
```

## 5. 综合示例

```python
class Fraction:
    """分数类"""

    def __init__(self, numerator, denominator):
        if denominator == 0:
            raise ValueError("分母不能为0")
        self.numerator = numerator
        self.denominator = denominator
        self._simplify()

    def _gcd(self, a, b):
        """计算最大公约数"""
        while b:
            a, b = b, a % b
        return a

    def _simplify(self):
        """化简分数"""
        g = self._gcd(abs(self.numerator), abs(self.denominator))
        self.numerator //= g
        self.denominator //= g
        if self.denominator < 0:
            self.numerator = -self.numerator
            self.denominator = -self.denominator

    def __add__(self, other):
        num = self.numerator * other.denominator + other.numerator * self.denominator
        den = self.denominator * other.denominator
        return Fraction(num, den)

    def __sub__(self, other):
        num = self.numerator * other.denominator - other.numerator * self.denominator
        den = self.denominator * other.denominator
        return Fraction(num, den)

    def __mul__(self, other):
        return Fraction(
            self.numerator * other.numerator,
            self.denominator * other.denominator
        )

    def __truediv__(self, other):
        return Fraction(
            self.numerator * other.denominator,
            self.denominator * other.numerator
        )

    def __eq__(self, other):
        return (self.numerator == other.numerator and
                self.denominator == other.denominator)

    def __str__(self):
        if self.denominator == 1:
            return str(self.numerator)
        return f"{self.numerator}/{self.denominator}"

    def __repr__(self):
        return f"Fraction({self.numerator}, {self.denominator})"

# 使用
f1 = Fraction(1, 2)
f2 = Fraction(1, 3)

print(f1 + f2)  # 5/6
print(f1 - f2)  # 1/6
print(f1 * f2)  # 1/6
print(f1 / f2)  # 3/2
```

## 6. 常见错误与调试

### 错误1：忘记调用 super().__init__()

```python
class Parent:
    def __init__(self, name):
        self.name = name

class Child(Parent):
    def __init__(self, name, age):
        # 忘记调用 super().__init__(name)
        self.age = age

c = Child("张三", 10)
# print(c.name)  # AttributeError: 'Child' object has no attribute 'name'
```

### 错误2：多重继承的方法解析顺序

```python
class A:
    def greet(self):
        print("A")

class B(A):
    def greet(self):
        print("B")

class C(A):
    def greet(self):
        print("C")

class D(B, C):
    pass

d = D()
d.greet()  # B（按照方法解析顺序MRO）
print(D.__mro__)  # 查看MRO
```

## 小结

本章学习了：
- 封装：隐藏内部实现，提供公开接口
- property装饰器的使用
- 继承：代码复用，建立类的层次结构
- super()调用父类方法
- 多态：同一接口，不同实现
- 常用魔术方法：__str__, __repr__, __eq__, __add__等

**练习建议**：
1. 创建一个员工管理系统，包含Employee基类和Manager、Engineer子类
2. 实现一个有理数类，支持四则运算
3. 创建一个游戏角色类，包含不同职业的子类
