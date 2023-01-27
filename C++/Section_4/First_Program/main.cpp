#include <iostream> // import iostream library

int main() // main function
{
    int favorite_number;                                           // initialize variable of type int
    std::cout << "Enter your favorite number between 1 and 100: "; // output to terminal

    std::cin >> favorite_number; // input from user on terminal and start new line

    std::cout << "Amazing!! That's my favorite number too!" << std::endl; // output to terminal and start new line

    return 0; // main returns an integer, setting 0 if everything works
}
