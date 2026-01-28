# 第五章：循环结构

## 5.1 while 循环

当条件为真时，重复执行代码块：

```c
#include <stdio.h>

int main() {
    int count = 1;

    while (count <= 5) {
        printf("第 %d 次循环\n", count);
        count++;
    }

    return 0;
}
```

### 语法结构

```c
while (条件) {
    // 循环体
}
```

### 实例：计算1到100的和

```c
#include <stdio.h>

int main() {
    int sum = 0;
    int i = 1;

    while (i <= 100) {
        sum += i;
        i++;
    }

    printf("1到100的和是: %d\n", sum);  // 5050
    return 0;
}
```

## 5.2 do-while 循环

先执行一次，再判断条件：

```c
#include <stdio.h>

int main() {
    int num;

    do {
        printf("请输入一个正数: ");
        scanf("%d", &num);
    } while (num <= 0);

    printf("你输入的正数是: %d\n", num);
    return 0;
}
```

### while 与 do-while 的区别

```c
// while: 可能一次都不执行
int x = 0;
while (x > 0) {
    printf("不会执行\n");
}

// do-while: 至少执行一次
int y = 0;
do {
    printf("会执行一次\n");
} while (y > 0);
```

## 5.3 for 循环

最常用的循环结构：

```c
#include <stdio.h>

int main() {
    for (int i = 1; i <= 5; i++) {
        printf("第 %d 次循环\n", i);
    }

    return 0;
}
```

### 语法结构

```c
for (初始化; 条件; 更新) {
    // 循环体
}
```

### 执行顺序

1. 执行初始化（只执行一次）
2. 判断条件
3. 如果条件为真，执行循环体
4. 执行更新表达式
5. 回到步骤2

### 实例：打印乘法表的一行

```c
#include <stdio.h>

int main() {
    int n = 5;

    for (int i = 1; i <= 9; i++) {
        printf("%d x %d = %d\n", n, i, n * i);
    }

    return 0;
}
```

## 5.4 嵌套循环

循环中包含循环：

```c
#include <stdio.h>

int main() {
    // 打印九九乘法表
    for (int i = 1; i <= 9; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d*%d=%d\t", j, i, i * j);
        }
        printf("\n");
    }

    return 0;
}
```

### 实例：打印矩形

```c
#include <stdio.h>

int main() {
    int rows = 4, cols = 6;

    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            printf("* ");
        }
        printf("\n");
    }

    return 0;
}
```

输出：
```
* * * * * *
* * * * * *
* * * * * *
* * * * * *
```

## 5.5 break 和 continue

### break：跳出循环

```c
#include <stdio.h>

int main() {
    for (int i = 1; i <= 10; i++) {
        if (i == 5) {
            break;  // 当 i=5 时跳出循环
        }
        printf("%d ", i);
    }
    // 输出: 1 2 3 4

    return 0;
}
```

### continue：跳过本次循环

```c
#include <stdio.h>

int main() {
    for (int i = 1; i <= 10; i++) {
        if (i % 2 == 0) {
            continue;  // 跳过偶数
        }
        printf("%d ", i);
    }
    // 输出: 1 3 5 7 9

    return 0;
}
```

## 5.6 循环综合实例

### 猜数字游戏

```c
#include <stdio.h>

int main() {
    int target = 42;  // 目标数字
    int guess;
    int attempts = 0;

    printf("猜数字游戏！范围是1-100\n");

    while (1) {
        printf("请输入你的猜测: ");
        scanf("%d", &guess);
        attempts++;

        if (guess < target) {
            printf("太小了！\n");
        } else if (guess > target) {
            printf("太大了！\n");
        } else {
            printf("恭喜你猜对了！用了 %d 次\n", attempts);
            break;
        }
    }

    return 0;
}
```

### 寻找素数

```c
#include <stdio.h>

int main() {
    int n = 50;

    printf("2到%d之间的素数:\n", n);

    for (int i = 2; i <= n; i++) {
        int isPrime = 1;

        for (int j = 2; j * j <= i; j++) {
            if (i % j == 0) {
                isPrime = 0;
                break;
            }
        }

        if (isPrime) {
            printf("%d ", i);
        }
    }
    printf("\n");

    return 0;
}
```

## 5.7 死循环

要小心避免无限循环：

```c
// 危险！这是一个死循环
while (1) {
    printf("无限循环\n");
}

// 正确做法：确保有退出条件
int count = 0;
while (count < 10) {
    printf("循环 %d\n", count);
    count++;  // 不要忘记更新变量！
}
```

## 本章小结

- `while`：先判断条件，再执行
- `do-while`：先执行一次，再判断条件
- `for`：适合已知循环次数的情况
- 嵌套循环用于处理二维数据
- `break` 跳出整个循环
- `continue` 跳过本次迭代
- 注意避免死循环
