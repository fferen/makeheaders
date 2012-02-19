#### Python script to generate and then update header files from C source files.

For each function in the provided file(s), creates a corresponding declaration
in the header file with the same name, or, if the function name already exists
there, updates the arguments, return type, and docstring. Does not modify
anything else in the header.

Functions must have a docstring before the definition to be discovered (that's
right, it enforces good coding style with an iron fist):

    /* documentation */
    TypeName func(arg, arg, ...) {
        foo;
        bar;
    }

Brace style and whitespace don't matter.

Static functions or those whose names start with "\_" are ignored.

---

I made this tool because while there exist tools like this already, I couldn't
find one that merely updates the headers while preserving existing structure
such as preprocessor directives, struct definitions, etc.

To be fair though, as I'm a DIY kind of person, I didn't look very hard. :)
