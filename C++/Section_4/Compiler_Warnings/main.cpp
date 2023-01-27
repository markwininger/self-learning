#include <iostream>

// compiler has recognized an issue with code that could lead to a potential problem
// compiler is still able to compile code despite issue

int main()
{
    int favorite_number; // initialize variable of type int, compiler warning, variable unused

    std::cout << "Hello World" << std::endl;
    return 0;
}
