/* Model absent PS2 memory-card roots on a host where ':' is not a valid
 * filename character. All other file operations use the host C library. */
#include <stdio.h>
#include <errno.h>
#include <string.h>
#undef fopen
#undef fgets
#undef ferror
#undef fclose
extern FILE *fopen(const char *path, const char *mode);
extern char *fgets(char *buffer, int size, FILE *file);
extern int ferror(FILE *file);
extern int fclose(FILE *file);
static int card_error = ENOENT;
static int card_read_error;
static FILE *fault_file;
void pops_test_set_card_error(int error) { card_error = error; }
void pops_test_set_card_read_error(int error) { card_read_error = error; fault_file = NULL; }
int pops_test_fclose(FILE *file) {
  if (file == fault_file) fault_file = NULL;
  return fclose(file);
}
char *pops_test_fgets(char *buffer, int size, FILE *file) {
  if (card_read_error && file == fault_file) { errno = card_read_error; return NULL; }
  return fgets(buffer, size, file);
}
int pops_test_ferror(FILE *file) {
  if (card_read_error && file == fault_file) { errno = card_read_error; return 1; }
  return ferror(file);
}
FILE *pops_test_fopen(const char *path, const char *mode) {
  if (!strncmp(path, "unavailable:", 12)) {
    errno = ENODEV;
    return NULL;
  }
  if (!strncmp(path, "mc0:", 4) || !strncmp(path, "mc1:", 4)) {
    if (card_read_error) { fault_file = tmpfile(); return fault_file; }
    errno = card_error;
    return NULL;
  }
  return fopen(path, mode);
}
