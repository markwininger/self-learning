#include <iostream>

// Linker is having trouble linking all the object files together to create an executable
// a library or object file may be missing
// will compile but fails to build

extern int x; // variable is defined outside program

int main() // main function
{
    std::cout << "Hello World" << std::endl;

    std::cout << x; // output to terminal, linker error because of undefined reference to x

    return 0;
}
