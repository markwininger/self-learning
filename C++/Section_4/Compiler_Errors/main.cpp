#include <iostream>

// Syntax errors - something wrong with the structure
// Semantic errors - something wrong with the meaning

int main()
    // compiler error due to missing beginning bracket
    std::cout
    << "Hello World" << std::endll;              // compiler error due to syntax for endl
std::cout << ("Hello World" / 125) << std::endl; // compiler error due to semantics
return                                           // compiler error if missing end of statement ";"
    return;                                      // compiler error if returns nothing
return "Joe";                                    // compiler error if incorrect type such as String
}
