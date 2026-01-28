# 第二章：数据类型与变量

## 2.1 变量的概念

**变量**是程序中用于存储数据的容器。在C语言中，使用变量前必须先**声明**。

```c
int age;        // 声明一个整型变量
age = 18;       // 给变量赋值

int score = 95; // 声明并初始化
```

### 变量命名规则

- 只能包含字母、数字和下划线
- 必须以字母或下划线开头
- 区分大小写（`age` 和 `Age` 是不同的变量）
- 不能使用C语言的关键字（如 `int`、`return` 等）

## 2.2 基本数据类型

### 整数类型

| 类型 | 大小 | 范围 |
|------|------|------|
| `int` | 4字节 | -2147483648 ~ 2147483647 |
| `short` | 2字节 | -32768 ~ 32767 |
| `long` | 4/8字节 | 更大范围 |
| `unsigned int` | 4字节 | 0 ~ 4294967295 |

```c
int number = 100;
short small = 10;
long big = 1000000L;
unsigned int positive = 500;
```

### 浮点类型

| 类型 | 大小 | 精度 |
|------|------|------|
| `float` | 4字节 | 6-7位有效数字 |
| `double` | 8字节 | 15-16位有效数字 |

```c
float pi = 3.14f;
double precise = 3.141592653589793;
```

### 字符类型

```c
char letter = 'A';
char digit = '5';
char newline = '\n';
```

> **注意**：字符用**单引号**，字符串用**双引号**

## 2.3 printf 格式化输出

使用**格式说明符**输出不同类型的变量：

```c
#include <stdio.h>

int main() {
    int age = 20;
    float height = 1.75f;
    char grade = 'A';

    printf("年龄: %d\n", age);
    printf("身高: %.2f 米\n", height);
    printf("等级: %c\n", grade);

    return 0;
}
```

### 常用格式说明符

| 说明符 | 用途 | 示例 |
|--------|------|------|
| `%d` | 整数 | `printf("%d", 10);` |
| `%f` | 浮点数 | `printf("%f", 3.14);` |
| `%.2f` | 保留2位小数 | `printf("%.2f", 3.14159);` |
| `%c` | 字符 | `printf("%c", 'A');` |
| `%s` | 字符串 | `printf("%s", "Hello");` |
| `%ld` | 长整型 | `printf("%ld", 100000L);` |

## 2.4 scanf 输入函数

使用 `scanf` 从键盘读取用户输入：

```c
#include <stdio.h>

int main() {
    int age;
    float score;

    printf("请输入你的年龄: ");
    scanf("%d", &age);

    printf("请输入你的分数: ");
    scanf("%f", &score);

    printf("你今年 %d 岁，得了 %.1f 分\n", age, score);

    return 0;
}
```

> **重要**：`scanf` 中变量前必须加 `&` 符号（取地址）

### 读取多个值

```c
int a, b;
printf("请输入两个整数（用空格分隔）: ");
scanf("%d %d", &a, &b);
printf("a = %d, b = %d\n", a, b);
```

## 2.5 常量

### 使用 const 定义常量

```c
const float PI = 3.14159f;
const int MAX_SIZE = 100;
```

### 使用 #define 定义宏常量

```c
#define PI 3.14159
#define MAX_SIZE 100
```

## 2.6 类型转换

### 自动类型转换

较小类型自动转换为较大类型：

```c
int a = 10;
float b = 3.5f;
float result = a + b;  // a 自动转换为 float
```

### 强制类型转换

```c
int a = 10;
int b = 3;
float result = (float)a / b;  // 结果为 3.333...
```

## 本章小结

- 变量是存储数据的容器，使用前需声明
- 基本数据类型：`int`、`float`、`double`、`char`
- 使用 `printf` 格式化输出，`scanf` 读取输入
- `scanf` 中变量需要加 `&` 取地址
- 可以使用 `const` 或 `#define` 定义常量
