#include <iostream>

// Errors that are mistakes of the programmer

int main() // main function
{
    int age;
    if (age > 18) // condition excludes 18 years from voting
    {
        std::cout << "Yes, you can vote!";
    }
    return 0;
}
