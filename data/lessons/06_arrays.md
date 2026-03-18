# 第六章：数组

## 6.1 数组的概念

**数组**是存储相同类型数据的集合，使用连续的内存空间。

```c
int scores[5];  // 声明一个包含5个整数的数组
```

### 数组的声明与初始化

```c
// 声明并初始化
int numbers[5] = {10, 20, 30, 40, 50};

// 部分初始化，其余元素为0
int arr[5] = {1, 2};  // {1, 2, 0, 0, 0}

// 自动确定大小
int values[] = {1, 2, 3, 4, 5};  // 大小为5

// 全部初始化为0
int zeros[10] = {0};
```

## 6.2 数组元素的访问

使用**下标**访问数组元素，下标从 **0** 开始：

```c
#include <stdio.h>

int main() {
    int scores[5] = {85, 90, 78, 92, 88};

    printf("第1个分数: %d\n", scores[0]);  // 85
    printf("第3个分数: %d\n", scores[2]);  // 78
    printf("第5个分数: %d\n", scores[4]);  // 88

    // 修改元素
    scores[2] = 80;
    printf("修改后第3个分数: %d\n", scores[2]);  // 80

    return 0;
}
```

> **注意**：数组下标从0开始，最大下标是 `长度 - 1`

## 6.3 遍历数组

使用循环遍历数组的所有元素：

```c
#include <stdio.h>

int main() {
    int numbers[5] = {10, 20, 30, 40, 50};
    int size = 5;

    // 遍历并打印
    printf("数组元素: ");
    for (int i = 0; i < size; i++) {
        printf("%d ", numbers[i]);
    }
    printf("\n");

    // 计算总和
    int sum = 0;
    for (int i = 0; i < size; i++) {
        sum += numbers[i];
    }
    printf("总和: %d\n", sum);
    printf("平均值: %.2f\n", (float)sum / size);

    return 0;
}
```

## 6.4 数组与函数

```c
#include <stdio.h>

// 数组作为参数时需要传递长度
void printArray(int arr[], int size) {
    for (int i = 0; i < size; i++) {
        printf("%d ", arr[i]);
    }
    printf("\n");
}

// 找最大值
int findMax(int arr[], int size) {
    int max = arr[0];
    for (int i = 1; i < size; i++) {
        if (arr[i] > max) {
            max = arr[i];
        }
    }
    return max;
}

int main() {
    int nums[] = {34, 67, 23, 89, 45};
    int size = 5;

    printArray(nums, size);
    printf("最大值: %d\n", findMax(nums, size));

    return 0;
}
```

## 6.5 二维数组

用于存储表格或矩阵数据：

```c
#include <stdio.h>

int main() {
    // 3行4列的二维数组
    int matrix[3][4] = {
        {1, 2, 3, 4},
        {5, 6, 7, 8},
        {9, 10, 11, 12}
    };

    // 访问元素
    printf("第2行第3列的元素: %d\n", matrix[1][2]);  // 7

    // 遍历二维数组
    printf("矩阵内容:\n");
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 4; j++) {
            printf("%3d ", matrix[i][j]);
        }
        printf("\n");
    }

    return 0;
}
```

## 6.6 字符数组与字符串

在C语言中，字符串是以 `\0` 结尾的字符数组：

```c
#include <stdio.h>

int main() {
    // 字符数组
    char name1[6] = {'H', 'e', 'l', 'l', 'o', '\0'};

    // 字符串字面量（自动添加 \0）
    char name2[] = "Hello";

    printf("%s\n", name1);  // Hello
    printf("%s\n", name2);  // Hello

    return 0;
}
```

### 字符串输入输出

```c
#include <stdio.h>

int main() {
    char name[50];

    printf("请输入你的名字: ");
    scanf("%s", name);  // 注意：不需要 &

    printf("你好, %s!\n", name);

    return 0;
}
```

> **注意**：`scanf("%s")` 遇到空格会停止读取

### 读取带空格的字符串

```c
#include <stdio.h>

int main() {
    char sentence[100];

    printf("请输入一句话: ");
    fgets(sentence, 100, stdin);  // 可以读取空格

    printf("你输入的是: %s", sentence);

    return 0;
}
```

## 6.7 字符串函数

使用 `<string.h>` 头文件：

```c
#include <stdio.h>
#include <string.h>

int main() {
    char str1[50] = "Hello";
    char str2[50] = "World";

    // 字符串长度
    printf("str1 的长度: %lu\n", strlen(str1));  // 5

    // 字符串复制
    char copy[50];
    strcpy(copy, str1);
    printf("复制: %s\n", copy);  // Hello

    // 字符串连接
    strcat(str1, " ");
    strcat(str1, str2);
    printf("连接: %s\n", str1);  // Hello World

    // 字符串比较
    if (strcmp("abc", "abc") == 0) {
        printf("字符串相等\n");
    }

    return 0;
}
```

### 常用字符串函数

| 函数 | 功能 |
|------|------|
| `strlen(s)` | 返回字符串长度 |
| `strcpy(dest, src)` | 复制字符串 |
| `strcat(dest, src)` | 连接字符串 |
| `strcmp(s1, s2)` | 比较字符串（相等返回0） |

## 6.8 数组实例：冒泡排序

```c
#include <stdio.h>

int main() {
    int arr[] = {64, 34, 25, 12, 22, 11, 90};
    int n = 7;

    // 冒泡排序
    for (int i = 0; i < n - 1; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                // 交换
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }

    // 输出排序结果
    printf("排序后: ");
    for (int i = 0; i < n; i++) {
        printf("%d ", arr[i]);
    }
    printf("\n");

    return 0;
}
```

## 本章小结

- 数组存储相同类型的多个元素
- 数组下标从0开始
- 使用循环遍历数组
- 二维数组用于表示矩阵或表格
- 字符串是以 `\0` 结尾的字符数组
- 使用 `<string.h>` 中的函数操作字符串
