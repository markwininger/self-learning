#include <iostream>

// Errors that occur during execution
// examples: divide by zero, file not found, out of memory, etc.
// Can be mitigated with exception handling

int main()
{

    std::cout << (11 / 0) << std::endl;
    return 0;
}
