# 异常处理

程序在运行时可能会遇到各种错误。异常处理让我们能够优雅地处理这些错误，而不是让程序崩溃。

## 1. 什么是异常？

异常是程序运行时发生的错误：

```python
# 除零错误
print(10 / 0)  # ZeroDivisionError: division by zero

# 类型错误
print("age: " + 18)  # TypeError: can only concatenate str (not "int") to str

# 索引错误
lst = [1, 2, 3]
print(lst[10])  # IndexError: list index out of range

# 键错误
d = {"name": "张三"}
print(d["age"])  # KeyError: 'age'

# 名称错误
print(undefined_variable)  # NameError: name 'undefined_variable' is not defined
```

## 2. try-except 基本语法

### 2.1 捕获异常

```python
try:
    # 可能出错的代码
    num = int(input("请输入一个数字："))
    result = 100 / num
    print(f"结果是：{result}")
except:
    # 出错时执行
    print("发生了错误！")
```

### 2.2 捕获特定异常

```python
try:
    num = int(input("请输入一个数字："))
    result = 100 / num
    print(f"结果是：{result}")
except ValueError:
    print("请输入有效的数字！")
except ZeroDivisionError:
    print("不能除以零！")
```

### 2.3 捕获多个异常

```python
try:
    num = int(input("请输入一个数字："))
    result = 100 / num
    print(f"结果是：{result}")
except (ValueError, ZeroDivisionError) as e:
    print(f"发生错误：{e}")
```

### 2.4 获取异常信息

```python
try:
    num = int(input("请输入一个数字："))
    result = 100 / num
except ValueError as e:
    print(f"值错误：{e}")
except ZeroDivisionError as e:
    print(f"除零错误：{e}")
except Exception as e:
    # 捕获所有其他异常
    print(f"未知错误：{e}")
```

## 3. try-except-else-finally

### 3.1 完整结构

```python
try:
    # 尝试执行的代码
    num = int(input("请输入一个数字："))
    result = 100 / num
except ValueError:
    # 值错误时执行
    print("请输入有效的数字！")
except ZeroDivisionError:
    # 除零错误时执行
    print("不能除以零！")
else:
    # 没有异常时执行
    print(f"计算成功，结果是：{result}")
finally:
    # 无论是否有异常都执行
    print("程序结束")
```

### 3.2 finally 的用途

`finally` 常用于清理资源：

```python
file = None
try:
    file = open("data.txt", "r")
    content = file.read()
    print(content)
except FileNotFoundError:
    print("文件不存在！")
finally:
    # 确保文件被关闭
    if file:
        file.close()
        print("文件已关闭")

# 更好的方式：使用 with 语句
try:
    with open("data.txt", "r") as file:
        content = file.read()
        print(content)
except FileNotFoundError:
    print("文件不存在！")
```

## 4. 常见异常类型

| 异常类型 | 说明 | 示例 |
|----------|------|------|
| ValueError | 值错误 | `int("abc")` |
| TypeError | 类型错误 | `"a" + 1` |
| ZeroDivisionError | 除零错误 | `1/0` |
| IndexError | 索引超出范围 | `[1,2][10]` |
| KeyError | 字典键不存在 | `{}["key"]` |
| FileNotFoundError | 文件不存在 | `open("xxx")` |
| AttributeError | 属性不存在 | `"a".xxx()` |
| NameError | 变量未定义 | `print(xxx)` |
| ImportError | 导入错误 | `import xxx` |
| StopIteration | 迭代器耗尽 | `next(iter([]))` |

### 异常层次结构

```
BaseException
 ├── SystemExit
 ├── KeyboardInterrupt
 ├── GeneratorExit
 └── Exception
      ├── ValueError
      ├── TypeError
      ├── IndexError
      ├── KeyError
      ├── FileNotFoundError
      ├── ZeroDivisionError
      └── ...
```

## 5. raise 抛出异常

### 5.1 基本用法

```python
def set_age(age):
    if age < 0:
        raise ValueError("年龄不能为负数")
    if age > 150:
        raise ValueError("年龄不能超过150")
    print(f"年龄设置为：{age}")

try:
    set_age(-5)
except ValueError as e:
    print(f"错误：{e}")
```

### 5.2 重新抛出异常

```python
def process_data(data):
    try:
        result = int(data)
        return result * 2
    except ValueError:
        print("日志：数据转换失败")
        raise  # 重新抛出当前异常

try:
    process_data("abc")
except ValueError as e:
    print(f"主程序捕获：{e}")
```

### 5.3 异常链

```python
def read_config():
    try:
        with open("config.txt") as f:
            return f.read()
    except FileNotFoundError as e:
        raise RuntimeError("配置文件读取失败") from e

try:
    read_config()
except RuntimeError as e:
    print(f"错误：{e}")
    print(f"原因：{e.__cause__}")
```

## 6. 自定义异常

### 6.1 创建自定义异常

```python
class MyError(Exception):
    """自定义异常基类"""
    pass

class ValidationError(MyError):
    """验证错误"""
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")

class NetworkError(MyError):
    """网络错误"""
    pass

# 使用自定义异常
def validate_email(email):
    if "@" not in email:
        raise ValidationError("email", "邮箱格式不正确")
    if len(email) < 5:
        raise ValidationError("email", "邮箱太短")
    return True

try:
    validate_email("abc")
except ValidationError as e:
    print(f"验证失败 - {e.field}: {e.message}")
```

### 6.2 更复杂的自定义异常

```python
class BankError(Exception):
    """银行相关异常基类"""
    pass

class InsufficientFundsError(BankError):
    """余额不足异常"""
    def __init__(self, balance, amount):
        self.balance = balance
        self.amount = amount
        super().__init__(
            f"余额不足：当前余额{balance}，尝试取款{amount}"
        )

class InvalidAmountError(BankError):
    """无效金额异常"""
    def __init__(self, amount):
        self.amount = amount
        super().__init__(f"无效金额：{amount}")

class BankAccount:
    def __init__(self, balance=0):
        self.balance = balance

    def withdraw(self, amount):
        if amount <= 0:
            raise InvalidAmountError(amount)
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount)
        self.balance -= amount
        return amount

# 使用
account = BankAccount(100)

try:
    account.withdraw(150)
except InsufficientFundsError as e:
    print(f"取款失败：{e}")
    print(f"当前余额：{e.balance}")
    print(f"尝试取款：{e.amount}")
except InvalidAmountError as e:
    print(f"金额错误：{e}")
```

## 7. 断言 (assert)

断言用于调试，确保条件为真：

```python
def calculate_average(numbers):
    assert len(numbers) > 0, "列表不能为空"
    return sum(numbers) / len(numbers)

# 正常情况
print(calculate_average([1, 2, 3, 4, 5]))  # 3.0

# 断言失败
try:
    print(calculate_average([]))
except AssertionError as e:
    print(f"断言失败：{e}")  # 断言失败：列表不能为空
```

> **注意**：断言可以通过 `-O` 参数禁用，不要用于生产环境的输入验证。

## 8. 实用技巧

### 8.1 异常处理最佳实践

```python
# 1. 捕获具体异常，不要捕获所有异常
# 不好
try:
    do_something()
except:
    pass

# 好
try:
    do_something()
except ValueError:
    handle_value_error()

# 2. 不要用异常控制流程
# 不好
try:
    value = my_dict[key]
except KeyError:
    value = default

# 好
value = my_dict.get(key, default)

# 3. 使用上下文管理器
# 不好
file = open("data.txt")
try:
    data = file.read()
finally:
    file.close()

# 好
with open("data.txt") as file:
    data = file.read()
```

### 8.2 记录异常信息

```python
import traceback

try:
    result = 1 / 0
except Exception as e:
    # 获取完整的错误堆栈
    error_info = traceback.format_exc()
    print("错误详情：")
    print(error_info)
```

### 8.3 处理多个操作

```python
def process_files(file_list):
    results = []
    errors = []

    for filename in file_list:
        try:
            with open(filename) as f:
                content = f.read()
                results.append((filename, content))
        except FileNotFoundError:
            errors.append((filename, "文件不存在"))
        except PermissionError:
            errors.append((filename, "没有读取权限"))

    return results, errors

# 使用
files = ["a.txt", "b.txt", "c.txt"]
success, failed = process_files(files)

print("成功处理：")
for name, content in success:
    print(f"  {name}")

print("处理失败：")
for name, error in failed:
    print(f"  {name}: {error}")
```

## 9. 常见错误与调试

### 错误1：异常捕获顺序

```python
# 错误：父类异常在前，子类永远不会被捕获
try:
    raise ValueError("test")
except Exception:  # 这会捕获所有异常
    print("Exception")
except ValueError:  # 永远不会执行到这里
    print("ValueError")

# 正确：子类异常在前
try:
    raise ValueError("test")
except ValueError:
    print("ValueError")
except Exception:
    print("Exception")
```

### 错误2：空的 except

```python
# 不好：吞掉所有异常
try:
    do_something()
except:
    pass  # 发生什么都不管

# 好：至少记录一下
try:
    do_something()
except Exception as e:
    print(f"发生错误：{e}")
    # 或者记录到日志
```

### 错误3：在 finally 中 return

```python
def test():
    try:
        return "try"
    finally:
        return "finally"  # 这会覆盖 try 中的返回值！

print(test())  # finally
```

## 10. 实际应用示例

```python
class DataProcessor:
    """数据处理器，演示完整的异常处理"""

    def __init__(self, filename):
        self.filename = filename
        self.data = None

    def load(self):
        """加载数据"""
        try:
            with open(self.filename, 'r', encoding='utf-8') as f:
                self.data = f.read()
            return True
        except FileNotFoundError:
            print(f"错误：文件 {self.filename} 不存在")
            return False
        except PermissionError:
            print(f"错误：没有权限读取 {self.filename}")
            return False
        except UnicodeDecodeError:
            print(f"错误：文件编码不正确")
            return False

    def process(self):
        """处理数据"""
        if self.data is None:
            raise RuntimeError("请先加载数据")

        try:
            # 模拟数据处理
            lines = self.data.split('\n')
            numbers = [int(line) for line in lines if line.strip()]
            return sum(numbers)
        except ValueError as e:
            raise ValueError(f"数据格式错误：{e}")

    def run(self):
        """运行处理器"""
        if not self.load():
            return None

        try:
            result = self.process()
            print(f"处理完成，结果：{result}")
            return result
        except ValueError as e:
            print(f"处理失败：{e}")
            return None
        except RuntimeError as e:
            print(f"运行错误：{e}")
            return None

# 使用
processor = DataProcessor("numbers.txt")
processor.run()
```

## 小结

本章学习了：
- 异常的概念和常见类型
- try-except-else-finally 结构
- raise 抛出异常
- 自定义异常类
- 断言 assert
- 异常处理最佳实践

**练习建议**：
1. 编写一个安全的除法函数，处理各种异常情况
2. 创建一个用户注册验证器，使用自定义异常
3. 实现一个文件处理程序，能够优雅地处理各种文件操作错误
