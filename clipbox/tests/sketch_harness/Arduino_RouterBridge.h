// Fake Arduino_RouterBridge for host tests: prints every notify, stores provided callbacks.
#pragma once
#include <cstdio>
#include <cstring>

unsigned long millis();

struct FakeBridge {
  void (*feedback)(int) = nullptr;
  void begin() {}
  void provide_safe(const char* name, void (*fn)(int)) {
    if (std::strcmp(name, "feedback") == 0) feedback = fn;
  }
  template <typename... Args>
  void notify(const char* name, Args... args) {
    std::printf("notify %s", name);
    int unpack[] = {0, (std::printf(" %d", static_cast<int>(args)), 0)...};
    (void)unpack;
    std::printf(" @%lu\n", millis());
  }
};

extern FakeBridge Bridge;
