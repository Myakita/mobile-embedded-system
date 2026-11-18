// Minimal test harness for the edge unit tests: a named case table and a CHECK that keeps going
// after a failure (and, unlike assert, is not compiled out under NDEBUG).
#pragma once

#include <cstdio>
#include <sstream>
#include <string>

namespace ut
{
struct Case
{
    const char* name;
    void (*fn)();
};

inline int& failures()
{
    static int count = 0;
    return count;
}

template <typename A, typename B>
void check_eq(const A& actual, const B& expected, const char* a_text, const char* file, int line)
{
    if (!(actual == expected))
    {
        std::ostringstream out;
        out << "  FAIL " << file << ':' << line << ": " << a_text << " == [" << actual << "], expected ["
            << expected << "]\n";
        std::fputs(out.str().c_str(), stderr);
        ++failures();
    }
}

template <std::size_t N> int run(const Case (&cases)[N])
{
    int failed = 0;
    for (const Case& test : cases)
    {
        const int before = failures();
        test.fn();
        const bool ok = failures() == before;
        std::printf("[%s] %s\n", ok ? " OK " : "FAIL", test.name);
        failed += ok ? 0 : 1;
    }
    std::printf("%zu cases, %d failed\n", N, failed);
    return failed == 0 ? 0 : 1;
}
} // namespace ut

#define CHECK(expr)                                                                                          \
    do                                                                                                       \
    {                                                                                                        \
        if (!(expr))                                                                                         \
        {                                                                                                    \
            std::fprintf(stderr, "  FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr);                           \
            ++ut::failures();                                                                                \
        }                                                                                                    \
    } while (0)

#define CHECK_EQ(actual, expected) ut::check_eq((actual), (expected), #actual, __FILE__, __LINE__)
