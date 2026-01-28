# 第八章：指针基础

## 8.1 什么是指针

**指针**是一个变量，它存储另一个变量的**内存地址**。

```c
#include <stdio.h>

int main() {
    int num = 42;
    int *ptr = &num;  // ptr 存储 num 的地址

    printf("num 的值: %d\n", num);
    printf("num 的地址: %p\n", &num);
    printf("ptr 存储的地址: %p\n", ptr);
    printf("ptr 指向的值: %d\n", *ptr);

    return 0;
}
```

### 关键概念

| 符号 | 含义 | 示例 |
|------|------|------|
| `&` | 取地址运算符 | `&num` 获取 num 的地址 |
| `*` | 解引用运算符 | `*ptr` 获取指针指向的值 |
| `*` | 声明指针类型 | `int *ptr` 声明指向 int 的指针 |

## 8.2 指针的声明与初始化

```c
int num = 10;
int *ptr = &num;   // 指向 int 的指针

float pi = 3.14f;
float *fptr = &pi; // 指向 float 的指针

char ch = 'A';
char *cptr = &ch;  // 指向 char 的指针
```

### 空指针

```c
int *ptr = NULL;  // 空指针，不指向任何地址

// 使用前检查
if (ptr != NULL) {
    printf("%d\n", *ptr);
}
```

## 8.3 通过指针修改变量

```c
#include <stdio.h>

int main() {
    int num = 10;
    int *ptr = &num;

    printf("修改前: %d\n", num);  // 10

    *ptr = 20;  // 通过指针修改 num 的值

    printf("修改后: %d\n", num);  // 20

    return 0;
}
```

## 8.4 指针与函数

### 通过指针实现"传址调用"

```c
#include <stdio.h>

// 交换两个数
void swap(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int main() {
    int x = 5, y = 10;

    printf("交换前: x=%d, y=%d\n", x, y);
    swap(&x, &y);  // 传递地址
    printf("交换后: x=%d, y=%d\n", x, y);

    return 0;
}
```

### 函数返回多个值

```c
#include <stdio.h>

// 计算商和余数
void divide(int a, int b, int *quotient, int *remainder) {
    *quotient = a / b;
    *remainder = a % b;
}

int main() {
    int q, r;
    divide(17, 5, &q, &r);
    printf("17 / 5 = %d 余 %d\n", q, r);

    return 0;
}
```

## 8.5 指针与数组

数组名是指向第一个元素的指针：

```c
#include <stdio.h>

int main() {
    int arr[] = {10, 20, 30, 40, 50};

    printf("arr 的地址: %p\n", arr);
    printf("&arr[0] 的地址: %p\n", &arr[0]);
    // 两者相同！

    // 通过指针访问数组
    int *ptr = arr;
    for (int i = 0; i < 5; i++) {
        printf("%d ", *(ptr + i));
    }
    printf("\n");

    return 0;
}
```

### 指针算术

```c
int arr[] = {10, 20, 30, 40, 50};
int *ptr = arr;

printf("%d\n", *ptr);       // 10 (arr[0])
printf("%d\n", *(ptr + 1)); // 20 (arr[1])
printf("%d\n", *(ptr + 2)); // 30 (arr[2])

ptr++;  // 指向下一个元素
printf("%d\n", *ptr);  // 20
```

## 8.6 指针与字符串

```c
#include <stdio.h>

int main() {
    char str[] = "Hello";
    char *ptr = str;

    // 遍历字符串
    while (*ptr != '\0') {
        printf("%c", *ptr);
        ptr++;
    }
    printf("\n");

    // 或者更简洁
    char *s = "World";
    printf("%s\n", s);

    return 0;
}
```

### 字符串指针 vs 字符数组

```c
char arr[] = "Hello";  // 可修改
char *ptr = "Hello";   // 字符串常量，不可修改

arr[0] = 'h';   // 正确
// ptr[0] = 'h';  // 危险！可能导致崩溃
```

## 8.7 指针数组

存储多个指针的数组：

```c
#include <stdio.h>

int main() {
    char *names[] = {"Alice", "Bob", "Charlie"};

    for (int i = 0; i < 3; i++) {
        printf("%s\n", names[i]);
    }

    return 0;
}
```

## 8.8 常见错误

### 1. 使用未初始化的指针

```c
int *ptr;       // 危险！未初始化
*ptr = 10;      // 可能导致崩溃

// 正确做法
int *ptr = NULL;
int num;
ptr = &num;
*ptr = 10;
```

### 2. 访问已释放的内存

```c
int *ptr;
{
    int local = 10;
    ptr = &local;
}
// local 已超出作用域
// *ptr 是危险的
```

### 3. 空指针解引用

```c
int *ptr = NULL;
// *ptr = 10;  // 错误！

// 正确做法
if (ptr != NULL) {
    *ptr = 10;
}
```

## 8.9 综合实例

### 用指针遍历并修改数组

```c
#include <stdio.h>

void doubleArray(int *arr, int size) {
    for (int i = 0; i < size; i++) {
        *(arr + i) *= 2;
    }
}

int main() {
    int nums[] = {1, 2, 3, 4, 5};
    int size = 5;

    printf("原数组: ");
    for (int i = 0; i < size; i++) {
        printf("%d ", nums[i]);
    }
    printf("\n");

    doubleArray(nums, size);

    printf("翻倍后: ");
    for (int i = 0; i < size; i++) {
        printf("%d ", nums[i]);
    }
    printf("\n");

    return 0;
}
```

### 找出数组中的最大值和最小值

```c
#include <stdio.h>

void findMinMax(int *arr, int size, int *min, int *max) {
    *min = *max = arr[0];

    for (int i = 1; i < size; i++) {
        if (arr[i] < *min) {
            *min = arr[i];
        }
        if (arr[i] > *max) {
            *max = arr[i];
        }
    }
}

int main() {
    int nums[] = {34, 12, 67, 45, 89, 23};
    int size = 6;
    int min, max;

    findMinMax(nums, size, &min, &max);

    printf("最小值: %d\n", min);
    printf("最大值: %d\n", max);

    return 0;
}
```

## 本章小结

- 指针存储变量的内存地址
- `&` 取地址，`*` 解引用
- 通过指针可以修改原变量（传址调用）
- 数组名是指向第一个元素的指针
- 使用指针前确保已正确初始化
- 使用空指针前要检查
- 指针是C语言最强大也最危险的特性，需要谨慎使用
