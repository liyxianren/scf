# 第四章：条件语句

## 4.1 if 语句

当条件为真时执行代码块：

```c
#include <stdio.h>

int main() {
    int score = 85;

    if (score >= 60) {
        printf("恭喜，考试及格了！\n");
    }

    return 0;
}
```

### 语法结构

```c
if (条件) {
    // 条件为真时执行的代码
}
```

## 4.2 if-else 语句

```c
#include <stdio.h>

int main() {
    int score = 55;

    if (score >= 60) {
        printf("及格\n");
    } else {
        printf("不及格\n");
    }

    return 0;
}
```

## 4.3 if-else if-else 多分支

```c
#include <stdio.h>

int main() {
    int score;
    printf("请输入分数: ");
    scanf("%d", &score);

    if (score >= 90) {
        printf("优秀 (A)\n");
    } else if (score >= 80) {
        printf("良好 (B)\n");
    } else if (score >= 70) {
        printf("中等 (C)\n");
    } else if (score >= 60) {
        printf("及格 (D)\n");
    } else {
        printf("不及格 (F)\n");
    }

    return 0;
}
```

## 4.4 嵌套 if 语句

```c
#include <stdio.h>

int main() {
    int age = 20;
    int hasLicense = 1;  // 1 表示有驾照

    if (age >= 18) {
        if (hasLicense) {
            printf("可以开车\n");
        } else {
            printf("年龄够了，但需要考驾照\n");
        }
    } else {
        printf("年龄不够，不能开车\n");
    }

    return 0;
}
```

## 4.5 条件运算符（三目运算符）

简洁的条件判断方式：

```c
条件 ? 值1 : 值2
```

```c
#include <stdio.h>

int main() {
    int a = 10, b = 20;

    // 找出较大值
    int max = (a > b) ? a : b;
    printf("较大的数是: %d\n", max);

    // 判断奇偶
    int num = 7;
    printf("%d 是 %s\n", num, (num % 2 == 0) ? "偶数" : "奇数");

    return 0;
}
```

## 4.6 switch 语句

适用于多个固定值的判断：

```c
#include <stdio.h>

int main() {
    int day;
    printf("请输入星期几（1-7）: ");
    scanf("%d", &day);

    switch (day) {
        case 1:
            printf("星期一\n");
            break;
        case 2:
            printf("星期二\n");
            break;
        case 3:
            printf("星期三\n");
            break;
        case 4:
            printf("星期四\n");
            break;
        case 5:
            printf("星期五\n");
            break;
        case 6:
            printf("星期六\n");
            break;
        case 7:
            printf("星期日\n");
            break;
        default:
            printf("输入无效\n");
    }

    return 0;
}
```

### switch 语法要点

1. `switch` 表达式必须是整型或字符型
2. 每个 `case` 后通常需要 `break`，否则会继续执行下一个 case
3. `default` 处理所有未匹配的情况

### case 穿透

有时故意省略 `break` 实现多个条件共享代码：

```c
switch (day) {
    case 1:
    case 2:
    case 3:
    case 4:
    case 5:
        printf("工作日\n");
        break;
    case 6:
    case 7:
        printf("周末\n");
        break;
}
```

## 4.7 实例：简易计算器

```c
#include <stdio.h>

int main() {
    float num1, num2, result;
    char op;

    printf("请输入表达式（如 5 + 3）: ");
    scanf("%f %c %f", &num1, &op, &num2);

    switch (op) {
        case '+':
            result = num1 + num2;
            break;
        case '-':
            result = num1 - num2;
            break;
        case '*':
            result = num1 * num2;
            break;
        case '/':
            if (num2 != 0) {
                result = num1 / num2;
            } else {
                printf("错误：除数不能为0\n");
                return 1;
            }
            break;
        default:
            printf("错误：不支持的运算符\n");
            return 1;
    }

    printf("%.2f %c %.2f = %.2f\n", num1, op, num2, result);
    return 0;
}
```

## 本章小结

- `if` 语句根据条件执行代码
- `if-else` 处理两种情况
- `if-else if-else` 处理多种情况
- 三目运算符是简洁的条件表达式
- `switch` 适用于固定值的多分支判断
- `switch` 中的 `break` 用于结束当前分支
