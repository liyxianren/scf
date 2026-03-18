# 第七章：函数

## 7.1 函数的概念

**函数**是执行特定任务的独立代码块，可以重复调用。

### 为什么使用函数？

- **代码复用**：避免重复编写相同代码
- **模块化**：将程序分解为独立的模块
- **易于维护**：修改函数不影响其他代码
- **提高可读性**：代码结构更清晰

## 7.2 函数的定义与调用

```c
#include <stdio.h>

// 函数定义
void sayHello() {
    printf("Hello, World!\n");
}

int main() {
    // 函数调用
    sayHello();
    sayHello();
    sayHello();

    return 0;
}
```

### 函数语法

```c
返回类型 函数名(参数列表) {
    // 函数体
    return 返回值;  // void 类型可省略
}
```

## 7.3 函数参数

### 带参数的函数

```c
#include <stdio.h>

// 带一个参数
void greet(char name[]) {
    printf("你好, %s!\n", name);
}

// 带两个参数
int add(int a, int b) {
    return a + b;
}

int main() {
    greet("小明");
    greet("小红");

    int sum = add(5, 3);
    printf("5 + 3 = %d\n", sum);

    return 0;
}
```

### 多个参数

```c
#include <stdio.h>

// 计算矩形面积
float rectangleArea(float width, float height) {
    return width * height;
}

int main() {
    float area = rectangleArea(5.0f, 3.0f);
    printf("矩形面积: %.2f\n", area);

    return 0;
}
```

## 7.4 返回值

### 返回单个值

```c
#include <stdio.h>

int max(int a, int b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}

// 使用三目运算符简化
int min(int a, int b) {
    return (a < b) ? a : b;
}

int main() {
    printf("较大值: %d\n", max(10, 20));
    printf("较小值: %d\n", min(10, 20));

    return 0;
}
```

### void 函数

不需要返回值时使用 `void`：

```c
void printLine() {
    printf("================\n");
}
```

## 7.5 函数声明（函数原型）

当函数定义在调用之后时，需要先声明：

```c
#include <stdio.h>

// 函数声明（原型）
int multiply(int a, int b);

int main() {
    int result = multiply(4, 5);
    printf("4 * 5 = %d\n", result);
    return 0;
}

// 函数定义
int multiply(int a, int b) {
    return a * b;
}
```

## 7.6 局部变量与全局变量

### 局部变量

在函数内部定义，只在该函数内有效：

```c
void test() {
    int x = 10;  // 局部变量
    printf("x = %d\n", x);
}
// x 在这里不可用
```

### 全局变量

在函数外部定义，所有函数都可访问：

```c
#include <stdio.h>

int counter = 0;  // 全局变量

void increment() {
    counter++;
}

int main() {
    increment();
    increment();
    printf("counter = %d\n", counter);  // 2
    return 0;
}
```

> **建议**：尽量少用全局变量，可能导致代码难以维护

## 7.7 递归函数

函数调用自身：

```c
#include <stdio.h>

// 计算阶乘: n! = n * (n-1) * ... * 1
int factorial(int n) {
    if (n <= 1) {
        return 1;  // 基准情况
    }
    return n * factorial(n - 1);  // 递归调用
}

int main() {
    printf("5! = %d\n", factorial(5));  // 120
    return 0;
}
```

### 递归的要素

1. **基准情况**：停止递归的条件
2. **递归调用**：函数调用自身，问题规模缩小

### 斐波那契数列

```c
#include <stdio.h>

int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main() {
    printf("斐波那契数列前10项:\n");
    for (int i = 0; i < 10; i++) {
        printf("%d ", fibonacci(i));
    }
    printf("\n");

    return 0;
}
```

## 7.8 传值调用

C语言默认是**传值调用**，函数接收参数的副本：

```c
#include <stdio.h>

void tryToChange(int x) {
    x = 100;  // 只修改副本
    printf("函数内 x = %d\n", x);
}

int main() {
    int a = 10;
    tryToChange(a);
    printf("函数外 a = %d\n", a);  // 仍然是 10

    return 0;
}
```

> 如果需要修改原变量，需要使用指针（下一章介绍）

## 7.9 常用标准库函数

### 数学函数 `<math.h>`

```c
#include <stdio.h>
#include <math.h>

int main() {
    printf("sqrt(16) = %.2f\n", sqrt(16));    // 4.00
    printf("pow(2, 10) = %.0f\n", pow(2, 10)); // 1024
    printf("abs(-5) = %d\n", abs(-5));         // 5
    printf("ceil(3.2) = %.0f\n", ceil(3.2));   // 4
    printf("floor(3.8) = %.0f\n", floor(3.8)); // 3

    return 0;
}
```

### 常用数学函数

| 函数 | 功能 |
|------|------|
| `sqrt(x)` | 平方根 |
| `pow(x, y)` | x的y次方 |
| `abs(x)` | 绝对值 |
| `ceil(x)` | 向上取整 |
| `floor(x)` | 向下取整 |
| `sin(x)`, `cos(x)` | 三角函数 |

## 7.10 综合实例

### 判断素数

```c
#include <stdio.h>

int isPrime(int n) {
    if (n <= 1) return 0;
    if (n <= 3) return 1;

    for (int i = 2; i * i <= n; i++) {
        if (n % i == 0) {
            return 0;
        }
    }
    return 1;
}

int main() {
    for (int i = 2; i <= 50; i++) {
        if (isPrime(i)) {
            printf("%d ", i);
        }
    }
    printf("\n");

    return 0;
}
```

## 本章小结

- 函数实现代码复用和模块化
- 函数可以有参数和返回值
- 局部变量在函数内有效，全局变量全程有效
- 递归函数调用自身，需要基准情况防止无限递归
- C语言默认传值调用，函数接收参数的副本
- 标准库提供了丰富的常用函数
