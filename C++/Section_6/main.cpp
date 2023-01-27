// Variables can contain letters, numbers, and underscores
// variables must begin with a letter or underscore
// variables cannot begin with a number
// variables cannot use reserved keywords
// cannot declare a name in the same scope
// c++ is case sensitive

// int 123;
// double 12.3;
// string "frank";
// account franks_account;
// person james;

// ****** style and best practices ******

// be consistent with naming convention
// avoid beginning names with underscores
// use meaningful names, not too long or too short
// never use variables be initializing them
// declare variables close to when you need them in your code

int age;      // uninitialized
int age = 21; // c-like initialization
int age(21);  // constructor initialization
int age{21};  // c++11 list initialization

// Fundamental data types implemented directly by the c++ language

// character types
// integer types signed and unsigned
// floating-point types
// boolean types

// size and precision is often compiler-dependent
// #include <climits>

// type size
// expressed in bits

// size (in bits) | representable values |
// 8 | 256 | 2^8
// 16 | 65,536 | 2^16
// 32 | 4,294,967,296 | 2^32
// 64 | 18,446,744,073,709,551,615 | 2^64

// character types
// used to represent single characters = 'A', 'X', '@'

// type name | size / precision
// char | 1 byte or at least 8 bits
// char16_t | at least 16 bits
// char32_t | at least 32 bits
// wchar_t | can represent the largest available character set

// integer types

// type name | size / precision
// signed short int | at least 16 bits
// signed int | at least 16 bits
// signed long int | at least 32 bits
// signed long long int | at least 64 bits
// unsigned short int | at least 16 bits
// unsigned int | at least 16 bits
// unsigned long int | at least 16 bits
// unsigned long long int | at least 64 bits

// signed - not necessary to explicitly state
// unsigned - necessary if int is explicitly non negative

// Floating-point Type

// represented by mantissa and exponent (scientific notation)
// precision is the number of digits in the mantissa
// precision and size are compiler dependent

// Type Name | Size / Typical Precision | Typical Range
// float | 7 decimal digits | 1.2 x 10^(-38) to 3.4 x 10^38
// double | no less than float / 15 decimal digits | 2.2 x 10^(-308) to 1.8 x 10^308
// long double | no less than double / 19 decimal digits | 3.3 x 10^(-4932) to 1.2 x 10^4932

// Boolean Type

// Used to represent true and false
// Zero is false
// Non-zero is true

// Type Name | Size / Precision
// bool | usually 8 bits true or false (C++ keywords)
