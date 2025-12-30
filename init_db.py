"""
数据库初始化脚本
运行此脚本来创建数据库表和初始数据
"""

import json
from app import app, db
from models import Lesson, Exercise


def init_lessons():
    """初始化教案数据"""
    lessons_data = [
        {
            "chapter_num": 1,
            "title": "Python基础",
            "description": "变量、数据类型、输入输出、运算符、类型转换",
            "content_file": "01_python_basics.md",
            "order_index": 1
        },
        {
            "chapter_num": 2,
            "title": "条件分支与循环",
            "description": "if/elif/else、比较运算符、逻辑运算符、for循环、while循环、break/continue",
            "content_file": "02_conditions_loops.md",
            "order_index": 2
        },
        {
            "chapter_num": 3,
            "title": "函数与方法",
            "description": "函数定义、参数类型、返回值、作用域、内置函数、lambda表达式",
            "content_file": "03_functions_methods.md",
            "order_index": 3
        },
        {
            "chapter_num": 4,
            "title": "列表与字典",
            "description": "列表操作、字典操作、切片、推导式、常用方法",
            "content_file": "04_list_dict.md",
            "order_index": 4
        },
        {
            "chapter_num": 5,
            "title": "类与对象",
            "description": "类定义、构造函数、实例属性、类属性、实例方法",
            "content_file": "05_class_object.md",
            "order_index": 5
        },
        {
            "chapter_num": 6,
            "title": "面向对象编程",
            "description": "封装、继承、多态、super()、魔术方法",
            "content_file": "06_oop.md",
            "order_index": 6
        },
        {
            "chapter_num": 7,
            "title": "异常处理",
            "description": "try/except/finally、raise、自定义异常、断言",
            "content_file": "07_exception.md",
            "order_index": 7
        }
    ]

    for data in lessons_data:
        lesson = Lesson(**data)
        db.session.add(lesson)

    db.session.commit()
    print(f"已添加 {len(lessons_data)} 个教案")


def init_exercises():
    """初始化练习题数据"""
    exercises_data = [
        # 第1章练习题
        {
            "lesson_id": 1,
            "title": "计算矩形面积",
            "description": "编写程序，输入矩形的长和宽（两个整数，各占一行），计算并输出矩形的面积。\n\n**示例输入：**\n```\n5\n3\n```\n\n**示例输出：**\n```\n15\n```",
            "difficulty": 1,
            "initial_code": "# 输入长和宽\nlength = int(input())\nwidth = int(input())\n\n# 计算面积并输出\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "5\n3", "expected_output": "15", "description": "测试 5×3"},
                    {"input": "10\n4", "expected_output": "40", "description": "测试 10×4"},
                    {"input": "1\n1", "expected_output": "1", "description": "测试 1×1"}
                ]
            }),
            "hint": "面积 = 长 × 宽，使用 * 运算符计算乘法",
            "solution": "length = int(input())\nwidth = int(input())\narea = length * width\nprint(area)"
        },
        {
            "lesson_id": 1,
            "title": "温度转换",
            "description": "编写程序，输入摄氏温度（浮点数），转换为华氏温度并输出（保留1位小数）。\n\n转换公式：华氏温度 = 摄氏温度 × 9/5 + 32\n\n**示例输入：**\n```\n100\n```\n\n**示例输出：**\n```\n212.0\n```",
            "difficulty": 1,
            "initial_code": "# 输入摄氏温度\ncelsius = float(input())\n\n# 转换为华氏温度并输出（保留1位小数）\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "100", "expected_output": "212.0", "description": "测试 100°C"},
                    {"input": "0", "expected_output": "32.0", "description": "测试 0°C"},
                    {"input": "37", "expected_output": "98.6", "description": "测试 37°C"}
                ]
            }),
            "hint": "使用公式计算，然后用 round(结果, 1) 保留1位小数",
            "solution": "celsius = float(input())\nfahrenheit = celsius * 9/5 + 32\nprint(round(fahrenheit, 1))"
        },
        {
            "lesson_id": 1,
            "title": "问候语生成",
            "description": "输入用户的姓名，输出问候语。格式为：`Hello, 姓名!`\n\n**示例输入：**\n```\n张三\n```\n\n**示例输出：**\n```\nHello, 张三!\n```",
            "difficulty": 1,
            "initial_code": "# 输入姓名\nname = input()\n\n# 输出问候语\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "张三", "expected_output": "Hello, 张三!", "description": "测试中文名"},
                    {"input": "Tom", "expected_output": "Hello, Tom!", "description": "测试英文名"},
                    {"input": "Python", "expected_output": "Hello, Python!", "description": "测试Python"}
                ]
            }),
            "hint": "使用 f-string 或字符串拼接：f'Hello, {name}!'",
            "solution": "name = input()\nprint(f'Hello, {name}!')"
        },
        {
            "lesson_id": 1,
            "title": "计算圆的面积",
            "description": "输入圆的半径（浮点数），计算并输出圆的面积（保留2位小数）。\n\nπ 取 3.14159\n\n**示例输入：**\n```\n5\n```\n\n**示例输出：**\n```\n78.54\n```",
            "difficulty": 1,
            "initial_code": "# 输入半径\nradius = float(input())\npi = 3.14159\n\n# 计算面积并输出（保留2位小数）\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "5", "expected_output": "78.54", "description": "半径为5"},
                    {"input": "1", "expected_output": "3.14", "description": "半径为1"},
                    {"input": "10", "expected_output": "314.16", "description": "半径为10"}
                ]
            }),
            "hint": "面积公式：S = π × r²，使用 round(结果, 2) 保留2位小数",
            "solution": "radius = float(input())\npi = 3.14159\narea = pi * radius ** 2\nprint(round(area, 2))"
        },
        {
            "lesson_id": 1,
            "title": "交换两个数",
            "description": "输入两个整数a和b（各占一行），交换它们的值后输出（每个数占一行）。\n\n**示例输入：**\n```\n10\n20\n```\n\n**示例输出：**\n```\n20\n10\n```",
            "difficulty": 1,
            "initial_code": "# 输入两个数\na = int(input())\nb = int(input())\n\n# 交换a和b的值\n# 在这里编写代码\n\n# 输出交换后的值\nprint(a)\nprint(b)\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "10\n20", "expected_output": "20\n10", "description": "交换10和20"},
                    {"input": "5\n8", "expected_output": "8\n5", "description": "交换5和8"},
                    {"input": "-1\n1", "expected_output": "1\n-1", "description": "交换-1和1"}
                ]
            }),
            "hint": "Python可以用 a, b = b, a 一行完成交换",
            "solution": "a = int(input())\nb = int(input())\na, b = b, a\nprint(a)\nprint(b)"
        },
        {
            "lesson_id": 1,
            "title": "计算BMI",
            "description": "输入体重（kg，浮点数）和身高（m，浮点数），计算BMI并输出（保留1位小数）。\n\nBMI公式：BMI = 体重 / 身高²\n\n**示例输入：**\n```\n70\n1.75\n```\n\n**示例输出：**\n```\n22.9\n```",
            "difficulty": 2,
            "initial_code": "# 输入体重和身高\nweight = float(input())\nheight = float(input())\n\n# 计算BMI并输出（保留1位小数）\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "70\n1.75", "expected_output": "22.9", "description": "正常体重"},
                    {"input": "80\n1.80", "expected_output": "24.7", "description": "偏重"},
                    {"input": "50\n1.60", "expected_output": "19.5", "description": "偏瘦"}
                ]
            }),
            "hint": "BMI = weight / (height ** 2)，用 round() 保留小数",
            "solution": "weight = float(input())\nheight = float(input())\nbmi = weight / (height ** 2)\nprint(round(bmi, 1))"
        },
        # 第2章练习题
        {
            "lesson_id": 2,
            "title": "判断奇偶数",
            "description": "输入一个整数，判断是奇数还是偶数。如果是偶数输出 `even`，否则输出 `odd`。\n\n**示例输入：**\n```\n4\n```\n\n**示例输出：**\n```\neven\n```",
            "difficulty": 1,
            "initial_code": "n = int(input())\n\n# 判断奇偶并输出\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "4", "expected_output": "even", "description": "测试偶数4"},
                    {"input": "7", "expected_output": "odd", "description": "测试奇数7"},
                    {"input": "0", "expected_output": "even", "description": "测试0"},
                    {"input": "-3", "expected_output": "odd", "description": "测试负奇数"}
                ]
            }),
            "hint": "使用取余运算符 %，如果 n % 2 == 0 则为偶数",
            "solution": "n = int(input())\nif n % 2 == 0:\n    print('even')\nelse:\n    print('odd')"
        },
        {
            "lesson_id": 2,
            "title": "计算1到N的和",
            "description": "输入一个正整数N，计算1到N的所有整数之和并输出。\n\n**示例输入：**\n```\n10\n```\n\n**示例输出：**\n```\n55\n```",
            "difficulty": 1,
            "initial_code": "n = int(input())\n\n# 计算1到n的和并输出\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "10", "expected_output": "55", "description": "1到10的和"},
                    {"input": "100", "expected_output": "5050", "description": "1到100的和"},
                    {"input": "1", "expected_output": "1", "description": "1到1的和"}
                ]
            }),
            "hint": "使用for循环和range()，或者使用公式 n*(n+1)//2",
            "solution": "n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)"
        },
        {
            "lesson_id": 2,
            "title": "打印乘法表",
            "description": "输入一个1-9的整数N，打印该数字的乘法口诀（从1到9）。每行格式为：`a*N=结果`\n\n**示例输入：**\n```\n3\n```\n\n**示例输出：**\n```\n1*3=3\n2*3=6\n3*3=9\n4*3=12\n5*3=15\n6*3=18\n7*3=21\n8*3=24\n9*3=27\n```",
            "difficulty": 2,
            "initial_code": "n = int(input())\n\n# 打印乘法表\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "3", "expected_output": "1*3=3\n2*3=6\n3*3=9\n4*3=12\n5*3=15\n6*3=18\n7*3=21\n8*3=24\n9*3=27", "description": "3的乘法表"},
                    {"input": "5", "expected_output": "1*5=5\n2*5=10\n3*5=15\n4*5=20\n5*5=25\n6*5=30\n7*5=35\n8*5=40\n9*5=45", "description": "5的乘法表"}
                ]
            }),
            "hint": "使用for循环遍历1到9，使用f-string格式化输出",
            "solution": "n = int(input())\nfor i in range(1, 10):\n    print(f'{i}*{n}={i*n}')"
        },
        {
            "lesson_id": 2,
            "title": "成绩等级",
            "description": "输入一个0-100的分数，输出对应的等级：\n- 90-100：A\n- 80-89：B\n- 70-79：C\n- 60-69：D\n- 0-59：F\n\n**示例输入：**\n```\n85\n```\n\n**示例输出：**\n```\nB\n```",
            "difficulty": 1,
            "initial_code": "score = int(input())\n\n# 判断等级并输出\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "95", "expected_output": "A", "description": "优秀"},
                    {"input": "85", "expected_output": "B", "description": "良好"},
                    {"input": "72", "expected_output": "C", "description": "中等"},
                    {"input": "65", "expected_output": "D", "description": "及格"},
                    {"input": "50", "expected_output": "F", "description": "不及格"}
                ]
            }),
            "hint": "使用 if-elif-else 结构判断分数区间",
            "solution": "score = int(input())\nif score >= 90:\n    print('A')\nelif score >= 80:\n    print('B')\nelif score >= 70:\n    print('C')\nelif score >= 60:\n    print('D')\nelse:\n    print('F')"
        },
        {
            "lesson_id": 2,
            "title": "判断闰年",
            "description": "输入一个年份，判断是否为闰年。\n\n闰年规则：\n- 能被4整除但不能被100整除\n- 或者能被400整除\n\n是闰年输出 `yes`，否则输出 `no`\n\n**示例输入：**\n```\n2024\n```\n\n**示例输出：**\n```\nyes\n```",
            "difficulty": 2,
            "initial_code": "year = int(input())\n\n# 判断是否为闰年\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "2024", "expected_output": "yes", "description": "2024是闰年"},
                    {"input": "2023", "expected_output": "no", "description": "2023不是闰年"},
                    {"input": "2000", "expected_output": "yes", "description": "2000是闰年"},
                    {"input": "1900", "expected_output": "no", "description": "1900不是闰年"}
                ]
            }),
            "hint": "使用逻辑运算符组合条件：(year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)",
            "solution": "year = int(input())\nif (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):\n    print('yes')\nelse:\n    print('no')"
        },
        {
            "lesson_id": 2,
            "title": "打印星号三角形",
            "description": "输入一个正整数n，打印n行的直角三角形。第i行有i个星号。\n\n**示例输入：**\n```\n4\n```\n\n**示例输出：**\n```\n*\n**\n***\n****\n```",
            "difficulty": 2,
            "initial_code": "n = int(input())\n\n# 打印星号三角形\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "4", "expected_output": "*\n**\n***\n****", "description": "4行三角形"},
                    {"input": "3", "expected_output": "*\n**\n***", "description": "3行三角形"},
                    {"input": "1", "expected_output": "*", "description": "1行三角形"}
                ]
            }),
            "hint": "使用for循环，每行打印 i 个星号，可以用 '*' * i",
            "solution": "n = int(input())\nfor i in range(1, n + 1):\n    print('*' * i)"
        },
        {
            "lesson_id": 2,
            "title": "求偶数和",
            "description": "输入一个正整数n，计算1到n之间所有偶数的和。\n\n**示例输入：**\n```\n10\n```\n\n**示例输出：**\n```\n30\n```\n（因为 2+4+6+8+10=30）",
            "difficulty": 1,
            "initial_code": "n = int(input())\n\n# 计算偶数和\n# 在这里编写代码\n",
            "test_cases": json.dumps({
                "test_type": "output",
                "cases": [
                    {"input": "10", "expected_output": "30", "description": "1-10偶数和"},
                    {"input": "5", "expected_output": "6", "description": "1-5偶数和(2+4)"},
                    {"input": "1", "expected_output": "0", "description": "1-1无偶数"}
                ]
            }),
            "hint": "在循环中用 if i % 2 == 0 判断偶数",
            "solution": "n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    if i % 2 == 0:\n        total += i\nprint(total)"
        },
        # 第3章练习题
        {
            "lesson_id": 3,
            "title": "计算平方",
            "description": "编写一个函数 `square(n)`，返回n的平方。\n\n**示例：**\n```python\nprint(square(5))  # 输出: 25\nprint(square(-3)) # 输出: 9\n```",
            "difficulty": 1,
            "initial_code": "def square(n):\n    # 返回n的平方\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "square",
                "function_tests": [
                    {"args": [5], "expected": 25},
                    {"args": [-3], "expected": 9},
                    {"args": [0], "expected": 0},
                    {"args": [10], "expected": 100}
                ]
            }),
            "hint": "使用 ** 运算符计算幂，或者使用 * 计算乘法",
            "solution": "def square(n):\n    return n ** 2"
        },
        {
            "lesson_id": 3,
            "title": "判断质数",
            "description": "编写一个函数 `is_prime(n)`，判断n是否为质数。如果是质数返回True，否则返回False。\n\n质数定义：大于1的自然数，除了1和它本身外，不能被其他自然数整除。\n\n**示例：**\n```python\nprint(is_prime(7))  # True\nprint(is_prime(4))  # False\n```",
            "difficulty": 2,
            "initial_code": "def is_prime(n):\n    # 判断n是否为质数\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "is_prime",
                "function_tests": [
                    {"args": [2], "expected": True},
                    {"args": [7], "expected": True},
                    {"args": [4], "expected": False},
                    {"args": [1], "expected": False},
                    {"args": [17], "expected": True},
                    {"args": [15], "expected": False}
                ]
            }),
            "hint": "先判断n是否小于2，然后检查2到sqrt(n)之间是否有能整除n的数",
            "solution": "def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True"
        },
        {
            "lesson_id": 3,
            "title": "计算阶乘",
            "description": "编写一个函数 `factorial(n)`，计算并返回n的阶乘（n!）。\n\n阶乘定义：n! = n × (n-1) × (n-2) × ... × 2 × 1，其中0! = 1\n\n**示例：**\n```python\nprint(factorial(5))  # 120\nprint(factorial(0))  # 1\n```",
            "difficulty": 2,
            "initial_code": "def factorial(n):\n    # 计算n的阶乘\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "factorial",
                "function_tests": [
                    {"args": [0], "expected": 1},
                    {"args": [1], "expected": 1},
                    {"args": [5], "expected": 120},
                    {"args": [10], "expected": 3628800}
                ]
            }),
            "hint": "可以使用循环或递归实现。循环方式：从1乘到n",
            "solution": "def factorial(n):\n    if n <= 1:\n        return 1\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result"
        },
        {
            "lesson_id": 3,
            "title": "斐波那契数列",
            "description": "编写一个函数 `fibonacci(n)`，返回第n个斐波那契数（从0开始计数）。\n\n斐波那契数列：0, 1, 1, 2, 3, 5, 8, 13, ...\n- F(0) = 0\n- F(1) = 1\n- F(n) = F(n-1) + F(n-2)\n\n**示例：**\n```python\nprint(fibonacci(0))  # 0\nprint(fibonacci(6))  # 8\n```",
            "difficulty": 2,
            "initial_code": "def fibonacci(n):\n    # 返回第n个斐波那契数\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "fibonacci",
                "function_tests": [
                    {"args": [0], "expected": 0},
                    {"args": [1], "expected": 1},
                    {"args": [6], "expected": 8},
                    {"args": [10], "expected": 55}
                ]
            }),
            "hint": "可以用循环迭代计算，保存前两个数",
            "solution": "def fibonacci(n):\n    if n <= 1:\n        return n\n    a, b = 0, 1\n    for _ in range(2, n + 1):\n        a, b = b, a + b\n    return b"
        },
        {
            "lesson_id": 3,
            "title": "最大公约数",
            "description": "编写一个函数 `gcd(a, b)`，计算两个正整数的最大公约数。\n\n**示例：**\n```python\nprint(gcd(12, 8))   # 4\nprint(gcd(17, 5))   # 1\n```",
            "difficulty": 2,
            "initial_code": "def gcd(a, b):\n    # 计算最大公约数\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "gcd",
                "function_tests": [
                    {"args": [12, 8], "expected": 4},
                    {"args": [17, 5], "expected": 1},
                    {"args": [100, 25], "expected": 25},
                    {"args": [7, 7], "expected": 7}
                ]
            }),
            "hint": "使用辗转相除法：gcd(a, b) = gcd(b, a % b)，直到 b 为 0",
            "solution": "def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a"
        },
        {
            "lesson_id": 3,
            "title": "回文判断",
            "description": "编写一个函数 `is_palindrome(s)`，判断字符串是否为回文（正读反读都一样）。\n\n**示例：**\n```python\nprint(is_palindrome('level'))  # True\nprint(is_palindrome('hello'))  # False\n```",
            "difficulty": 1,
            "initial_code": "def is_palindrome(s):\n    # 判断是否为回文\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "is_palindrome",
                "function_tests": [
                    {"args": ["level"], "expected": True},
                    {"args": ["hello"], "expected": False},
                    {"args": ["a"], "expected": True},
                    {"args": ["noon"], "expected": True},
                    {"args": ["ab"], "expected": False}
                ]
            }),
            "hint": "可以用切片 s[::-1] 反转字符串，然后比较",
            "solution": "def is_palindrome(s):\n    return s == s[::-1]"
        },
        # 第4章练习题
        {
            "lesson_id": 4,
            "title": "列表求和",
            "description": "编写一个函数 `list_sum(lst)`，返回列表中所有数字的和。\n\n**示例：**\n```python\nprint(list_sum([1, 2, 3, 4, 5]))  # 15\nprint(list_sum([]))  # 0\n```",
            "difficulty": 1,
            "initial_code": "def list_sum(lst):\n    # 返回列表元素的和\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "list_sum",
                "function_tests": [
                    {"args": [[1, 2, 3, 4, 5]], "expected": 15},
                    {"args": [[]], "expected": 0},
                    {"args": [[10]], "expected": 10},
                    {"args": [[-1, 1, -2, 2]], "expected": 0}
                ]
            }),
            "hint": "可以使用内置函数sum()，或者用循环累加",
            "solution": "def list_sum(lst):\n    return sum(lst)"
        },
        {
            "lesson_id": 4,
            "title": "找最大值",
            "description": "编写一个函数 `find_max(lst)`，返回列表中的最大值。不使用内置max函数。\n\n**示例：**\n```python\nprint(find_max([3, 1, 4, 1, 5, 9]))  # 9\nprint(find_max([-5, -2, -8]))  # -2\n```",
            "difficulty": 2,
            "initial_code": "def find_max(lst):\n    # 找出列表中的最大值（不使用max函数）\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "find_max",
                "function_tests": [
                    {"args": [[3, 1, 4, 1, 5, 9]], "expected": 9},
                    {"args": [[-5, -2, -8]], "expected": -2},
                    {"args": [[42]], "expected": 42},
                    {"args": [[1, 1, 1]], "expected": 1}
                ]
            }),
            "hint": "用第一个元素初始化最大值，然后遍历比较",
            "solution": "def find_max(lst):\n    if not lst:\n        return None\n    max_val = lst[0]\n    for num in lst[1:]:\n        if num > max_val:\n            max_val = num\n    return max_val"
        },
        {
            "lesson_id": 4,
            "title": "统计字符",
            "description": "编写一个函数 `count_chars(s)`，统计字符串中每个字符出现的次数，返回一个字典。\n\n**示例：**\n```python\nprint(count_chars('hello'))  # {'h': 1, 'e': 1, 'l': 2, 'o': 1}\n```",
            "difficulty": 2,
            "initial_code": "def count_chars(s):\n    # 统计每个字符出现的次数\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "count_chars",
                "function_tests": [
                    {"args": ["hello"], "expected": {"h": 1, "e": 1, "l": 2, "o": 1}},
                    {"args": ["aaa"], "expected": {"a": 3}},
                    {"args": [""], "expected": {}},
                    {"args": ["ab"], "expected": {"a": 1, "b": 1}}
                ]
            }),
            "hint": "遍历字符串，使用字典存储计数，可以用dict.get()方法",
            "solution": "def count_chars(s):\n    result = {}\n    for char in s:\n        result[char] = result.get(char, 0) + 1\n    return result"
        },
        {
            "lesson_id": 4,
            "title": "列表去重",
            "description": "编写一个函数 `remove_duplicates(lst)`，去除列表中的重复元素，保持原有顺序，返回新列表。\n\n**示例：**\n```python\nprint(remove_duplicates([1, 2, 2, 3, 1, 4]))  # [1, 2, 3, 4]\n```",
            "difficulty": 2,
            "initial_code": "def remove_duplicates(lst):\n    # 去除重复元素，保持顺序\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "remove_duplicates",
                "function_tests": [
                    {"args": [[1, 2, 2, 3, 1, 4]], "expected": [1, 2, 3, 4]},
                    {"args": [[1, 1, 1]], "expected": [1]},
                    {"args": [[]], "expected": []},
                    {"args": [[5, 4, 3, 2, 1]], "expected": [5, 4, 3, 2, 1]}
                ]
            }),
            "hint": "遍历列表，用一个集合记录已出现的元素",
            "solution": "def remove_duplicates(lst):\n    seen = set()\n    result = []\n    for item in lst:\n        if item not in seen:\n            seen.add(item)\n            result.append(item)\n    return result"
        },
        {
            "lesson_id": 4,
            "title": "合并字典",
            "description": "编写一个函数 `merge_dicts(d1, d2)`，合并两个字典。如果有相同的键，值相加。\n\n**示例：**\n```python\nprint(merge_dicts({'a': 1, 'b': 2}, {'b': 3, 'c': 4}))  \n# {'a': 1, 'b': 5, 'c': 4}\n```",
            "difficulty": 2,
            "initial_code": "def merge_dicts(d1, d2):\n    # 合并两个字典，相同键的值相加\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "merge_dicts",
                "function_tests": [
                    {"args": [{"a": 1, "b": 2}, {"b": 3, "c": 4}], "expected": {"a": 1, "b": 5, "c": 4}},
                    {"args": [{}, {"a": 1}], "expected": {"a": 1}},
                    {"args": [{"x": 10}, {}], "expected": {"x": 10}},
                    {"args": [{"a": 1}, {"a": 2}], "expected": {"a": 3}}
                ]
            }),
            "hint": "先复制第一个字典，然后遍历第二个字典进行合并",
            "solution": "def merge_dicts(d1, d2):\n    result = d1.copy()\n    for key, value in d2.items():\n        result[key] = result.get(key, 0) + value\n    return result"
        },
        {
            "lesson_id": 4,
            "title": "列表反转",
            "description": "编写一个函数 `reverse_list(lst)`，反转列表并返回新列表。不使用内置的reverse()方法或切片[::-1]。\n\n**示例：**\n```python\nprint(reverse_list([1, 2, 3, 4]))  # [4, 3, 2, 1]\n```",
            "difficulty": 1,
            "initial_code": "def reverse_list(lst):\n    # 反转列表（不使用reverse或[::-1]）\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "reverse_list",
                "function_tests": [
                    {"args": [[1, 2, 3, 4]], "expected": [4, 3, 2, 1]},
                    {"args": [[1]], "expected": [1]},
                    {"args": [[]], "expected": []},
                    {"args": [["a", "b", "c"]], "expected": ["c", "b", "a"]}
                ]
            }),
            "hint": "从后向前遍历原列表，或者使用循环交换首尾元素",
            "solution": "def reverse_list(lst):\n    result = []\n    for i in range(len(lst) - 1, -1, -1):\n        result.append(lst[i])\n    return result"
        },
        # 第5章练习题
        {
            "lesson_id": 5,
            "title": "创建矩形类",
            "description": "创建一个 `Rectangle` 类，包含：\n- 构造函数接收长和宽\n- `area()` 方法返回面积\n- `perimeter()` 方法返回周长\n\n**示例：**\n```python\nrect = Rectangle(4, 5)\nprint(rect.area())       # 20\nprint(rect.perimeter())  # 18\n```",
            "difficulty": 2,
            "initial_code": "class Rectangle:\n    def __init__(self, width, height):\n        # 初始化长和宽\n        pass\n    \n    def area(self):\n        # 返回面积\n        pass\n    \n    def perimeter(self):\n        # 返回周长\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_rectangle",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "面积 = 长 × 宽，周长 = 2 × (长 + 宽)",
            "solution": "class Rectangle:\n    def __init__(self, width, height):\n        self.width = width\n        self.height = height\n    \n    def area(self):\n        return self.width * self.height\n    \n    def perimeter(self):\n        return 2 * (self.width + self.height)\n\ndef test_rectangle():\n    r1 = Rectangle(4, 5)\n    r2 = Rectangle(3, 3)\n    return r1.area() == 20 and r1.perimeter() == 18 and r2.area() == 9"
        },
        {
            "lesson_id": 5,
            "title": "创建计数器类",
            "description": "创建一个 `Counter` 类，包含：\n- 构造函数初始化计数为0\n- `increment()` 方法增加1\n- `decrement()` 方法减少1\n- `get_count()` 方法返回当前计数\n\n**示例：**\n```python\nc = Counter()\nc.increment()\nc.increment()\nprint(c.get_count())  # 2\nc.decrement()\nprint(c.get_count())  # 1\n```",
            "difficulty": 1,
            "initial_code": "class Counter:\n    def __init__(self):\n        # 初始化计数为0\n        pass\n    \n    def increment(self):\n        # 计数加1\n        pass\n    \n    def decrement(self):\n        # 计数减1\n        pass\n    \n    def get_count(self):\n        # 返回当前计数\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_counter",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "使用self.count存储计数值",
            "solution": "class Counter:\n    def __init__(self):\n        self.count = 0\n    \n    def increment(self):\n        self.count += 1\n    \n    def decrement(self):\n        self.count -= 1\n    \n    def get_count(self):\n        return self.count\n\ndef test_counter():\n    c = Counter()\n    c.increment()\n    c.increment()\n    if c.get_count() != 2:\n        return False\n    c.decrement()\n    return c.get_count() == 1"
        },
        {
            "lesson_id": 5,
            "title": "创建学生类",
            "description": "创建一个 `Student` 类，包含：\n- 构造函数接收姓名和年龄\n- `introduce()` 方法返回 \"I am 姓名, 年龄 years old\"\n- `have_birthday()` 方法让年龄加1\n\n**示例：**\n```python\ns = Student('Tom', 18)\nprint(s.introduce())  # \"I am Tom, 18 years old\"\ns.have_birthday()\nprint(s.introduce())  # \"I am Tom, 19 years old\"\n```",
            "difficulty": 1,
            "initial_code": "class Student:\n    def __init__(self, name, age):\n        # 初始化姓名和年龄\n        pass\n    \n    def introduce(self):\n        # 返回自我介绍字符串\n        pass\n    \n    def have_birthday(self):\n        # 年龄加1\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_student",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "使用 self.name 和 self.age 存储属性",
            "solution": "class Student:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n    \n    def introduce(self):\n        return f'I am {self.name}, {self.age} years old'\n    \n    def have_birthday(self):\n        self.age += 1\n\ndef test_student():\n    s = Student('Tom', 18)\n    if s.introduce() != 'I am Tom, 18 years old':\n        return False\n    s.have_birthday()\n    return s.introduce() == 'I am Tom, 19 years old'"
        },
        {
            "lesson_id": 5,
            "title": "创建银行账户类",
            "description": "创建一个 `BankAccount` 类，包含：\n- 构造函数接收初始余额（默认为0）\n- `deposit(amount)` 方法存款\n- `withdraw(amount)` 方法取款，余额不足返回False\n- `get_balance()` 方法返回当前余额\n\n**示例：**\n```python\nacc = BankAccount(100)\nacc.deposit(50)\nprint(acc.get_balance())  # 150\nprint(acc.withdraw(200))  # False\nprint(acc.withdraw(100))  # True\nprint(acc.get_balance())  # 50\n```",
            "difficulty": 2,
            "initial_code": "class BankAccount:\n    def __init__(self, balance=0):\n        # 初始化余额\n        pass\n    \n    def deposit(self, amount):\n        # 存款\n        pass\n    \n    def withdraw(self, amount):\n        # 取款，余额不足返回False\n        pass\n    \n    def get_balance(self):\n        # 返回余额\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_bank_account",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "withdraw方法需要先检查余额是否足够",
            "solution": "class BankAccount:\n    def __init__(self, balance=0):\n        self.balance = balance\n    \n    def deposit(self, amount):\n        self.balance += amount\n    \n    def withdraw(self, amount):\n        if amount > self.balance:\n            return False\n        self.balance -= amount\n        return True\n    \n    def get_balance(self):\n        return self.balance\n\ndef test_bank_account():\n    acc = BankAccount(100)\n    acc.deposit(50)\n    if acc.get_balance() != 150:\n        return False\n    if acc.withdraw(200) != False:\n        return False\n    if acc.withdraw(100) != True:\n        return False\n    return acc.get_balance() == 50"
        },
        {
            "lesson_id": 5,
            "title": "创建栈类",
            "description": "创建一个 `Stack` 类，实现栈数据结构：\n- `push(item)` 压入元素\n- `pop()` 弹出并返回栈顶元素，栈空返回None\n- `peek()` 返回栈顶元素但不弹出，栈空返回None\n- `is_empty()` 判断栈是否为空\n\n**示例：**\n```python\ns = Stack()\ns.push(1)\ns.push(2)\nprint(s.peek())   # 2\nprint(s.pop())    # 2\nprint(s.pop())    # 1\nprint(s.is_empty())  # True\n```",
            "difficulty": 2,
            "initial_code": "class Stack:\n    def __init__(self):\n        # 初始化空栈\n        pass\n    \n    def push(self, item):\n        # 压入元素\n        pass\n    \n    def pop(self):\n        # 弹出栈顶元素\n        pass\n    \n    def peek(self):\n        # 返回栈顶元素\n        pass\n    \n    def is_empty(self):\n        # 判断是否为空\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_stack",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "使用列表存储元素，append添加，pop弹出",
            "solution": "class Stack:\n    def __init__(self):\n        self.items = []\n    \n    def push(self, item):\n        self.items.append(item)\n    \n    def pop(self):\n        if self.is_empty():\n            return None\n        return self.items.pop()\n    \n    def peek(self):\n        if self.is_empty():\n            return None\n        return self.items[-1]\n    \n    def is_empty(self):\n        return len(self.items) == 0\n\ndef test_stack():\n    s = Stack()\n    if not s.is_empty():\n        return False\n    s.push(1)\n    s.push(2)\n    if s.peek() != 2:\n        return False\n    if s.pop() != 2:\n        return False\n    if s.pop() != 1:\n        return False\n    return s.is_empty()"
        },
        # 第6章练习题
        {
            "lesson_id": 6,
            "title": "动物继承",
            "description": "创建一个 `Animal` 基类和 `Dog` 子类：\n\n`Animal` 类：\n- 构造函数接收name\n- `speak()` 方法返回 \"Some sound\"\n\n`Dog` 类继承 `Animal`：\n- 重写 `speak()` 方法返回 \"{name} says Woof!\"\n\n**示例：**\n```python\ndog = Dog(\"Buddy\")\nprint(dog.speak())  # \"Buddy says Woof!\"\n```",
            "difficulty": 2,
            "initial_code": "class Animal:\n    def __init__(self, name):\n        pass\n    \n    def speak(self):\n        pass\n\nclass Dog(Animal):\n    def speak(self):\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_animal",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "Dog类使用super().__init__(name)调用父类构造函数",
            "solution": "class Animal:\n    def __init__(self, name):\n        self.name = name\n    \n    def speak(self):\n        return 'Some sound'\n\nclass Dog(Animal):\n    def speak(self):\n        return f'{self.name} says Woof!'\n\ndef test_animal():\n    a = Animal('Generic')\n    d = Dog('Buddy')\n    return a.speak() == 'Some sound' and d.speak() == 'Buddy says Woof!'"
        },
        {
            "lesson_id": 6,
            "title": "形状类继承",
            "description": "创建形状类继承体系：\n\n`Shape` 基类：\n- `area()` 方法返回 0\n\n`Circle` 类继承 `Shape`：\n- 构造函数接收半径 radius\n- 重写 `area()` 返回圆面积（π取3.14）\n\n`Square` 类继承 `Shape`：\n- 构造函数接收边长 side\n- 重写 `area()` 返回正方形面积\n\n**示例：**\n```python\nc = Circle(5)\nprint(c.area())  # 78.5\ns = Square(4)\nprint(s.area())  # 16\n```",
            "difficulty": 2,
            "initial_code": "class Shape:\n    def area(self):\n        return 0\n\nclass Circle(Shape):\n    def __init__(self, radius):\n        pass\n    \n    def area(self):\n        pass\n\nclass Square(Shape):\n    def __init__(self, side):\n        pass\n    \n    def area(self):\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_shapes",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "圆面积 = π × r²，正方形面积 = 边长²",
            "solution": "class Shape:\n    def area(self):\n        return 0\n\nclass Circle(Shape):\n    def __init__(self, radius):\n        self.radius = radius\n    \n    def area(self):\n        return 3.14 * self.radius ** 2\n\nclass Square(Shape):\n    def __init__(self, side):\n        self.side = side\n    \n    def area(self):\n        return self.side ** 2\n\ndef test_shapes():\n    c = Circle(5)\n    s = Square(4)\n    base = Shape()\n    return c.area() == 78.5 and s.area() == 16 and base.area() == 0"
        },
        {
            "lesson_id": 6,
            "title": "员工类继承",
            "description": "创建员工类继承体系：\n\n`Employee` 基类：\n- 构造函数接收 name 和 salary\n- `get_salary()` 返回薪水\n\n`Manager` 类继承 `Employee`：\n- 构造函数额外接收 bonus\n- 重写 `get_salary()` 返回 薪水 + 奖金\n\n**示例：**\n```python\ne = Employee('Tom', 5000)\nprint(e.get_salary())  # 5000\nm = Manager('Jerry', 8000, 2000)\nprint(m.get_salary())  # 10000\n```",
            "difficulty": 2,
            "initial_code": "class Employee:\n    def __init__(self, name, salary):\n        pass\n    \n    def get_salary(self):\n        pass\n\nclass Manager(Employee):\n    def __init__(self, name, salary, bonus):\n        pass\n    \n    def get_salary(self):\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_employee",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "Manager使用super().__init__(name, salary)初始化父类，然后设置self.bonus",
            "solution": "class Employee:\n    def __init__(self, name, salary):\n        self.name = name\n        self.salary = salary\n    \n    def get_salary(self):\n        return self.salary\n\nclass Manager(Employee):\n    def __init__(self, name, salary, bonus):\n        super().__init__(name, salary)\n        self.bonus = bonus\n    \n    def get_salary(self):\n        return self.salary + self.bonus\n\ndef test_employee():\n    e = Employee('Tom', 5000)\n    m = Manager('Jerry', 8000, 2000)\n    return e.get_salary() == 5000 and m.get_salary() == 10000"
        },
        {
            "lesson_id": 6,
            "title": "向量类与运算符重载",
            "description": "创建一个 `Vector` 类，表示二维向量：\n- 构造函数接收 x 和 y\n- 实现 `__add__` 方法支持向量相加\n- 实现 `__str__` 方法返回 \"Vector(x, y)\"\n\n**示例：**\n```python\nv1 = Vector(1, 2)\nv2 = Vector(3, 4)\nv3 = v1 + v2\nprint(v3)  # \"Vector(4, 6)\"\n```",
            "difficulty": 3,
            "initial_code": "class Vector:\n    def __init__(self, x, y):\n        pass\n    \n    def __add__(self, other):\n        # 返回新的Vector对象\n        pass\n    \n    def __str__(self):\n        pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_vector",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "__add__方法返回一个新的Vector对象，x和y分别相加",
            "solution": "class Vector:\n    def __init__(self, x, y):\n        self.x = x\n        self.y = y\n    \n    def __add__(self, other):\n        return Vector(self.x + other.x, self.y + other.y)\n    \n    def __str__(self):\n        return f'Vector({self.x}, {self.y})'\n\ndef test_vector():\n    v1 = Vector(1, 2)\n    v2 = Vector(3, 4)\n    v3 = v1 + v2\n    return str(v3) == 'Vector(4, 6)'"
        },
        {
            "lesson_id": 6,
            "title": "多态练习",
            "description": "创建一个函数 `make_sounds(animals)` 接收动物列表，返回所有动物叫声的列表。\n\n提供三个类：\n- `Cat` 的 `speak()` 返回 \"Meow\"\n- `Dog` 的 `speak()` 返回 \"Woof\"\n- `Bird` 的 `speak()` 返回 \"Tweet\"\n\n**示例：**\n```python\nanimals = [Cat(), Dog(), Bird()]\nprint(make_sounds(animals))  # ['Meow', 'Woof', 'Tweet']\n```",
            "difficulty": 2,
            "initial_code": "class Cat:\n    def speak(self):\n        pass\n\nclass Dog:\n    def speak(self):\n        pass\n\nclass Bird:\n    def speak(self):\n        pass\n\ndef make_sounds(animals):\n    # 返回所有动物叫声的列表\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_polymorphism",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "遍历animals列表，调用每个动物的speak()方法",
            "solution": "class Cat:\n    def speak(self):\n        return 'Meow'\n\nclass Dog:\n    def speak(self):\n        return 'Woof'\n\nclass Bird:\n    def speak(self):\n        return 'Tweet'\n\ndef make_sounds(animals):\n    return [animal.speak() for animal in animals]\n\ndef test_polymorphism():\n    animals = [Cat(), Dog(), Bird()]\n    sounds = make_sounds(animals)\n    return sounds == ['Meow', 'Woof', 'Tweet']"
        },
        # 第7章练习题
        {
            "lesson_id": 7,
            "title": "安全除法",
            "description": "编写一个函数 `safe_divide(a, b)`，安全地计算 a/b：\n- 正常情况返回 a/b 的结果（浮点数）\n- 如果 b 为 0，返回字符串 \"Error: Division by zero\"\n- 如果输入不是数字，返回字符串 \"Error: Invalid input\"\n\n**示例：**\n```python\nprint(safe_divide(10, 2))   # 5.0\nprint(safe_divide(10, 0))   # \"Error: Division by zero\"\nprint(safe_divide('a', 2))  # \"Error: Invalid input\"\n```",
            "difficulty": 2,
            "initial_code": "def safe_divide(a, b):\n    # 实现安全除法\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "safe_divide",
                "function_tests": [
                    {"args": [10, 2], "expected": 5.0},
                    {"args": [10, 0], "expected": "Error: Division by zero"},
                    {"args": ["a", 2], "expected": "Error: Invalid input"},
                    {"args": [9, 3], "expected": 3.0}
                ]
            }),
            "hint": "使用try-except捕获ZeroDivisionError和TypeError",
            "solution": "def safe_divide(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return 'Error: Division by zero'\n    except TypeError:\n        return 'Error: Invalid input'"
        },
        {
            "lesson_id": 7,
            "title": "验证年龄",
            "description": "编写一个函数 `validate_age(age)`，验证年龄：\n- 如果age是有效年龄（0-150的整数），返回True\n- 如果age小于0，抛出 ValueError，消息为 \"Age cannot be negative\"\n- 如果age大于150，抛出 ValueError，消息为 \"Age cannot exceed 150\"\n- 如果age不是整数，抛出 TypeError，消息为 \"Age must be an integer\"\n\n**示例：**\n```python\nprint(validate_age(25))   # True\nvalidate_age(-5)          # 抛出 ValueError\nvalidate_age(200)         # 抛出 ValueError\nvalidate_age(\"25\")        # 抛出 TypeError\n```",
            "difficulty": 2,
            "initial_code": "def validate_age(age):\n    # 验证年龄\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_validate_age",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "使用isinstance()检查类型，使用raise抛出异常",
            "solution": "def validate_age(age):\n    if not isinstance(age, int):\n        raise TypeError('Age must be an integer')\n    if age < 0:\n        raise ValueError('Age cannot be negative')\n    if age > 150:\n        raise ValueError('Age cannot exceed 150')\n    return True\n\ndef test_validate_age():\n    try:\n        if not validate_age(25):\n            return False\n        if not validate_age(0):\n            return False\n        if not validate_age(150):\n            return False\n    except:\n        return False\n    \n    try:\n        validate_age(-5)\n        return False\n    except ValueError as e:\n        if str(e) != 'Age cannot be negative':\n            return False\n    \n    try:\n        validate_age(200)\n        return False\n    except ValueError as e:\n        if str(e) != 'Age cannot exceed 150':\n            return False\n    \n    try:\n        validate_age('25')\n        return False\n    except TypeError as e:\n        if str(e) != 'Age must be an integer':\n            return False\n    \n    return True"
        },
        {
            "lesson_id": 7,
            "title": "安全列表访问",
            "description": "编写一个函数 `safe_get(lst, index, default=None)`，安全地获取列表元素：\n- 正常情况返回 lst[index]\n- 如果索引越界，返回 default 值\n\n**示例：**\n```python\nprint(safe_get([1, 2, 3], 1))       # 2\nprint(safe_get([1, 2, 3], 10))      # None\nprint(safe_get([1, 2, 3], 10, -1))  # -1\n```",
            "difficulty": 1,
            "initial_code": "def safe_get(lst, index, default=None):\n    # 安全获取列表元素\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "safe_get",
                "function_tests": [
                    {"args": [[1, 2, 3], 1], "expected": 2},
                    {"args": [[1, 2, 3], 10], "expected": None},
                    {"args": [[1, 2, 3], 10, -1], "expected": -1},
                    {"args": [[], 0, "empty"], "expected": "empty"}
                ]
            }),
            "hint": "使用try-except捕获IndexError异常",
            "solution": "def safe_get(lst, index, default=None):\n    try:\n        return lst[index]\n    except IndexError:\n        return default"
        },
        {
            "lesson_id": 7,
            "title": "字符串转整数",
            "description": "编写一个函数 `str_to_int(s)`，将字符串转换为整数：\n- 成功返回整数\n- 失败返回字符串 \"Invalid number\"\n\n**示例：**\n```python\nprint(str_to_int('123'))   # 123\nprint(str_to_int('-45'))   # -45\nprint(str_to_int('abc'))   # \"Invalid number\"\nprint(str_to_int('12.5'))  # \"Invalid number\"\n```",
            "difficulty": 1,
            "initial_code": "def str_to_int(s):\n    # 字符串转整数\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "str_to_int",
                "function_tests": [
                    {"args": ["123"], "expected": 123},
                    {"args": ["-45"], "expected": -45},
                    {"args": ["abc"], "expected": "Invalid number"},
                    {"args": ["12.5"], "expected": "Invalid number"}
                ]
            }),
            "hint": "使用try-except捕获ValueError异常",
            "solution": "def str_to_int(s):\n    try:\n        return int(s)\n    except ValueError:\n        return 'Invalid number'"
        },
        {
            "lesson_id": 7,
            "title": "自定义异常",
            "description": "创建一个自定义异常类 `NegativeNumberError`，继承自 `ValueError`。\n\n编写函数 `calculate_sqrt(n)`：\n- 如果n为负数，抛出 `NegativeNumberError`，消息为 \"Cannot calculate square root of negative number\"\n- 否则返回n的平方根（使用 n ** 0.5）\n\n**示例：**\n```python\nprint(calculate_sqrt(16))  # 4.0\ncalculate_sqrt(-4)  # 抛出 NegativeNumberError\n```",
            "difficulty": 3,
            "initial_code": "class NegativeNumberError(ValueError):\n    pass\n\ndef calculate_sqrt(n):\n    # 计算平方根，负数抛出异常\n    pass\n",
            "test_cases": json.dumps({
                "test_type": "function",
                "function_name": "test_sqrt",
                "function_tests": [
                    {"args": [], "expected": True}
                ]
            }),
            "hint": "自定义异常类只需继承ValueError即可，raise抛出时传入错误消息",
            "solution": "class NegativeNumberError(ValueError):\n    pass\n\ndef calculate_sqrt(n):\n    if n < 0:\n        raise NegativeNumberError('Cannot calculate square root of negative number')\n    return n ** 0.5\n\ndef test_sqrt():\n    if calculate_sqrt(16) != 4.0:\n        return False\n    if calculate_sqrt(0) != 0.0:\n        return False\n    try:\n        calculate_sqrt(-4)\n        return False\n    except NegativeNumberError as e:\n        if str(e) != 'Cannot calculate square root of negative number':\n            return False\n    return True"
        }
    ]

    for data in exercises_data:
        exercise = Exercise(**data)
        db.session.add(exercise)

    db.session.commit()
    print(f"已添加 {len(exercises_data)} 道练习题")


def init_database():
    """初始化数据库"""
    with app.app_context():
        # 删除所有表并重新创建
        db.drop_all()
        db.create_all()
        print("数据库表已创建")

        # 添加初始数据
        init_lessons()
        init_exercises()

        print("\n数据库初始化完成！")
        print("运行 'python app.py' 启动服务器")


if __name__ == "__main__":
    init_database()
