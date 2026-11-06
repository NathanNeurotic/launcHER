#include "ipconfig_smap.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

static void accepts(const char *text, size_t length, const char *expected) {
  char ip[16] = {0};
  assert(smap_parse_ipconfig(text, length, ip));
  assert(!strcmp(ip, expected));
}
static void rejects(const char *text, size_t length) {
  char ip[16] = "unchanged";
  assert(!smap_parse_ipconfig(text, length, ip));
  assert(!strcmp(ip, "unchanged"));
}
int main(void) {
  accepts("192.168.0.10 255.255.255.0 192.168.0.1",
          sizeof("192.168.0.10 255.255.255.0 192.168.0.1") - 1, "192.168.0.10");
  accepts("10.0.0.2", 8, "10.0.0.2"); /* no whitespace or NUL in file */
  accepts("255.255.255.255", 15, "255.255.255.255");
  accepts(" \r\n\t172.16.1.99\n255.255.0.0", 27, "172.16.1.99");
  accepts("1.2.3.4 extra data", 18, "1.2.3.4");
  rejects("1.2.3", 5);
  rejects("999.2.3.4", 9);
  rejects("192.168.1.256", 13);
  rejects("1.2.3.4.5", 9);
  rejects("1..3.4", 6);
  rejects("1.2.3.A", 7);
  rejects("", 0);
  rejects("1234567890123456", 16);
  rejects("1.2.3.4", 4); /* truncated input, not a guessed success */
  rejects(NULL, 0);
  assert(!smap_parse_ipconfig("1.2.3.4", 7, NULL));
  puts("SMAP IPCONFIG bounded IPv4 parser PASS");
  return 0;
}
