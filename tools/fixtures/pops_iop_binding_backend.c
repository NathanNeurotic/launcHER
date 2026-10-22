/* Controlled in-memory storage behind the production POPFS driver. This
 * executes in the actual IOP kernel; it is not a physical-media emulator. */
#include <irx.h>
#include <iomanX.h>
#include <loadcore.h>
#include <sysclib.h>
#include <stdio.h>
#include <errno.h>

IRX_ID("pops_binding_test_backend", 1, 0);
static unsigned char cards[2][131072];
static struct handle { int used, slot, position; } handles[8];

static int init(iomanX_iop_device_t *dev) { (void)dev; return 0; }
static int slot(const char *name) {
  if (*name == '/') ++name;
  if (!strcmp(name, "disc")) return 0;
  if (!strcmp(name, "card0")) return 1;
  if (!strcmp(name, "card1")) return 2;
  return -ENOENT;
}
static int open_file(iomanX_iop_file_t *f, const char *name, int flags, int mode) {
  (void)mode;
  int selected = slot(name);
  if (selected < 0) return selected;
  if (!selected && (flags & 3) != FIO_O_RDONLY) return -EROFS;
  for (unsigned i = 0; i < 8; ++i) if (!handles[i].used) {
    handles[i].used = 1; handles[i].slot = selected; handles[i].position = 0;
    f->privdata = &handles[i]; return 0;
  }
  return -EMFILE;
}
static int close_file(iomanX_iop_file_t *f) {
  struct handle *h = f->privdata;
  if (!h) return -EBADF;
  h->used = 0; f->privdata = NULL; return 0;
}
static int read_file(iomanX_iop_file_t *f, void *buffer, int length) {
  struct handle *h = f->privdata;
  if (!h || length < 0) return -EINVAL;
  int end = h->slot ? 131072 : 16 * 1024 * 1024;
  if (length > end - h->position) length = end - h->position;
  if (h->slot) {
    memcpy(buffer, cards[h->slot - 1] + h->position, length);
    printf("POPS_IOP_BINDING backend-read slot=%d position=%d length=%d first=%u,%u,%u,%u\n",
        h->slot, h->position, length, ((unsigned char *)buffer)[0], ((unsigned char *)buffer)[1],
        ((unsigned char *)buffer)[2], ((unsigned char *)buffer)[3]);
  }
  else for (int i = 0; i < length; ++i)
    ((unsigned char *)buffer)[i] = (h->position + i) % 251;
  h->position += length; return length;
}
static int write_file(iomanX_iop_file_t *f, void *buffer, int length) {
  struct handle *h = f->privdata;
  if (!h || length < 0) return -EINVAL;
  if (!h->slot) return -EROFS;
  if (length > 131072 - h->position) length = 131072 - h->position;
  memcpy(cards[h->slot - 1] + h->position, buffer, length);
  printf("POPS_IOP_BINDING backend-write slot=%d position=%d length=%d first=%u,%u,%u,%u\n",
      h->slot, h->position, length, ((unsigned char *)buffer)[0], ((unsigned char *)buffer)[1],
      ((unsigned char *)buffer)[2], ((unsigned char *)buffer)[3]);
  h->position += length; return length;
}
static int seek_file(iomanX_iop_file_t *f, int offset, int whence) {
  struct handle *h = f->privdata;
  if (!h) return -EBADF;
  int end = h->slot ? 131072 : 16 * 1024 * 1024;
  int position = whence == 0 ? offset : whence == 1 ? h->position + offset :
                 whence == 2 ? end + offset : -1;
  if (position < 0 || position > end) return -EINVAL;
  h->position = position; return position;
}
static int sync_file(iomanX_iop_file_t *f, const char *name, int flags) {
  (void)f; (void)name; (void)flags; return 0;
}
IOMANX_RETURN_VALUE_IMPL(ENOSYS);
static iomanX_iop_device_ops_t ops = {
  .init = init, .deinit = init, .open = open_file, .close = close_file,
  .read = read_file, .write = write_file, .lseek = seek_file, .sync = sync_file,
  .format = IOMANX_RETURN_VALUE(ENOSYS), .ioctl = IOMANX_RETURN_VALUE(ENOSYS),
  .remove = IOMANX_RETURN_VALUE(ENOSYS), .mkdir = IOMANX_RETURN_VALUE(ENOSYS),
  .rmdir = IOMANX_RETURN_VALUE(ENOSYS), .dopen = IOMANX_RETURN_VALUE(ENOSYS),
  .dclose = IOMANX_RETURN_VALUE(ENOSYS), .dread = IOMANX_RETURN_VALUE(ENOSYS),
  .getstat = IOMANX_RETURN_VALUE(ENOSYS), .chstat = IOMANX_RETURN_VALUE(ENOSYS)
};
static iomanX_iop_device_t device = {"trace", IOP_DT_FS | IOP_DT_FSEXT, 1,
                                    "Controlled POPFS binding fixture", &ops};
int _start(int argc, char **argv) {
  printf("POPS_IOP_BINDING backend argc=%d argv0=%s\n", argc,
         argc && argv && argv[0] ? argv[0] : "NULL");
  return iomanX_AddDrv(&device) < 0 ? MODULE_NO_RESIDENT_END : MODULE_RESIDENT_END;
}
