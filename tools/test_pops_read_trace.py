#!/usr/bin/env python3
"""Exercise the trace-only fileXio comparison and retained dependency errors."""
import ctypes as c
import errno
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReadTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=os.name == 'nt')
        directory = Path(cls.temp.name)
        (directory / 'fileXio_rpc.h').write_text('''
#include <stdint.h>
int fileXioOpen(const char *, int);
int64_t fileXioLseek64(int, int64_t, int);
int fileXioRead(int, void *, int);
int fileXioClose(int);
''')
        (directory / 'io_common.h').write_text('#define FIO_O_RDONLY 0x0001\n')
        source = (ROOT / 'launcher/src/handler_pops.c').read_text()
        start = source.index('static int readFullFile(')
        end = source.index('/* The archived MAIN calls root TROJAN', start)
        wrapper = directory / 'wrapper.c'
        wrapper.write_text('''
#include "pops_read_trace.h"
#include "dprintf.h"
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#ifndef O_BINARY
#define O_BINARY 0
#endif
static int mode, posix_failure, real_fd, closes, reads;
static char trace[16384];
void test_reset(int next_mode, int next_posix_failure) {
  mode=next_mode;posix_failure=next_posix_failure;closes=reads=0;trace[0]=0;
}
const char *test_log(void) { return trace; }
int test_closes(void) { return closes; }
int test_reads(void) { return reads; }
int boot_trace_printf(const char *format, ...) {
  /* The target links newlib nano without long-long printf support. */
  assert(strstr(format,"%ll")==NULL);
  size_t used=strlen(trace);va_list args;va_start(args,format);
  int result=vsnprintf(trace+used,sizeof(trace)-used,format,args);
  va_end(args);return result;
}
int fileXioOpen(const char *path, int flags) {
  assert(flags==0x0001);
  if(mode==1) return -EACCES;
  real_fd=open(path,O_RDONLY|O_BINARY);
  return real_fd<0?-errno:0; /* Descriptor zero is a valid open. */
}
int64_t fileXioLseek64(int fd, int64_t offset, int whence) {
  assert(fd==0);
  if(whence==SEEK_END&&mode==2) return -EIO;
  if(whence==SEEK_SET&&mode==3) return 1;
  off_t result=lseek(real_fd,(off_t)offset,whence);
  return result<0?-errno:result;
}
int fileXioRead(int fd, void *buffer, int size) {
  assert(fd==0&&((uintptr_t)buffer&63)==0&&size>0&&size<=16384);
  ++reads;
  if(mode==4) return 0;
  if(mode==5) return size+1;
  if(mode==6) return -EACCES;
  ssize_t result=read(real_fd,buffer,size>7?7:size);
  return result<0?-errno:(int)result;
}
int fileXioClose(int fd) {
  assert(fd==0);++closes;
  int result=close(real_fd);
  return mode==7?-EIO:(result<0?-errno:(mode==8?3:result));
}
static ssize_t test_posix_read(int fd, void *buffer, size_t size) {
  if(posix_failure) { errno=EIO;return -1; }
  return read(fd,buffer,size);
}
static int test_posix_open(const char *path, int flags) {
  return open(path,flags|O_BINARY);
}
static int test_posix_close(int fd) {
  int result=close(fd);
  if(result<0) return result;
  if(mode==9) { errno=EIO; return 3; }
  if(mode==10) { errno=EACCES; return -1; }
  if(mode==11) { errno=0; return -1; }
  return result;
}
#define open test_posix_open
#define close test_posix_close
#define read test_posix_read
''' + source[start:end] + '''
int test_dependency(const char *path, void *buffer, size_t capacity, size_t *out) {
  return readPopsDependency(path,buffer,capacity,out);
}
''')
        library = directory / ('read_trace.dll' if os.name == 'nt' else 'read_trace.so')
        subprocess.run(['gcc', '-shared', '-fPIC', '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-DLAUNCHER_BOOT_TRACE', '-I', str(directory),
                        '-I', str(ROOT / 'common/include'), '-I', str(ROOT / 'launcher/include'),
                        str(wrapper), str(ROOT / 'launcher/src/pops_read_trace.c'),
                        str(ROOT / 'common/src/pops_profile.c'),
                        str(ROOT / 'common/src/pops_iop_image.c'),
                        str(ROOT / 'common/src/pops_external.c'), '-o', str(library)], check=True)
        cls.lib = c.CDLL(str(library))
        cls.lib.pops_read_filexio_trace.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t]
        cls.lib.test_dependency.argtypes = [c.c_char_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
        cls.lib.test_reset.argtypes = [c.c_int, c.c_int]
        cls.lib.test_log.restype = c.c_char_p

    @classmethod
    def tearDownClass(cls):
        if os.name == 'nt' and hasattr(cls, 'lib') and getattr(cls.lib, '_handle', None):
            c.windll.kernel32.FreeLibrary.argtypes = [c.c_void_p]
            c.windll.kernel32.FreeLibrary(cls.lib._handle)
        cls.temp.cleanup()

    def setUp(self):
        self.lib.test_reset(0, 0)
        self.data = bytes(i % 251 for i in range(32771))
        self.path = Path(self.temp.name) / 'owned.bin'
        self.path.write_bytes(self.data)
        self.buffer = c.create_string_buffer(b'X' * (len(self.data)+64))

    def compare(self, capacity=None):
        return self.lib.pops_read_filexio_trace(os.fsencode(self.path), self.buffer,
                                                len(self.data) if capacity is None else capacity)

    def test_aligned_short_reads_and_complete_hash(self):
        self.assertEqual(self.compare(), 0)
        self.assertEqual(self.buffer.raw[:len(self.data)], self.data)
        self.assertEqual(self.buffer.raw[len(self.data):len(self.data)+64], b'X'*64)
        self.assertGreater(self.lib.test_reads(), 2)
        self.assertEqual(self.lib.test_closes(), 1)
        log = self.lib.test_log().decode()
        self.assertIn(f'size_low={len(self.data)} size_high=0 capacity={len(self.data)}', log)
        self.assertIn('sha256='+hashlib.sha256(self.data).hexdigest(), log)

    def test_oversize_and_empty_fail_without_buffer_writes(self):
        for data, capacity in ((self.data, 8), (b'', 64)):
            self.lib.test_reset(0, 0)
            self.path.write_bytes(data)
            before = self.buffer.raw
            self.assertEqual(self.compare(capacity), -errno.EINVAL)
            self.assertEqual(self.buffer.raw, before)
            self.assertEqual(self.lib.test_reads(), 0)
            self.assertEqual(self.lib.test_closes(), 1)

    def test_positive_driver_close_is_success(self):
        self.lib.test_reset(8, 0)
        self.assertEqual(self.compare(), 0)
        self.assertEqual(self.lib.test_closes(), 1)
        self.assertIn(('sha256='+hashlib.sha256(self.data).hexdigest()).encode(),
                      self.lib.test_log())
        self.assertNotIn(b'POPS_XIO_FAIL', self.lib.test_log())

    def test_positive_close_comparison_retains_original_error(self):
        self.lib.test_reset(8, 1)
        size = c.c_size_t(0x1234)
        self.assertEqual(self.lib.test_dependency(os.fsencode(self.path), self.buffer,
                         len(self.data), c.byref(size)), -errno.EIO)
        self.assertEqual(size.value, 0x1234)
        self.assertIn(b'POPS_XIO complete', self.lib.test_log())
        self.assertIn(b'original_result=-5 retained', self.lib.test_log())

    def test_io_failures_close_once_and_report_stage(self):
        for mode, error, stage in ((1, errno.EACCES, 'open'), (2, errno.EIO, 'size'),
                                    (3, errno.EIO, 'rewind'), (4, errno.EIO, 'read'),
                                    (5, errno.EIO, 'read'), (6, errno.EACCES, 'read'),
                                    (7, errno.EIO, 'close')):
            with self.subTest(mode=mode):
                self.lib.test_reset(mode, 0)
                self.assertEqual(self.compare(), -error)
                self.assertIn(('POPS_XIO_FAIL stage='+stage).encode(), self.lib.test_log())
                self.assertEqual(self.lib.test_closes(), 0 if mode==1 else 1)
                if mode!=7:
                    self.assertEqual(self.buffer.raw[:len(self.data)], b'X'*len(self.data))

    def test_successful_comparison_never_replaces_original_failure(self):
        self.lib.test_reset(0, 1)
        size = c.c_size_t(0x1234)
        result = self.lib.test_dependency(os.fsencode(self.path), self.buffer,
                                          len(self.data), c.byref(size))
        self.assertEqual(result, -errno.EIO)
        self.assertEqual(size.value, 0x1234)
        self.assertEqual(self.buffer.raw[:len(self.data)], self.data)
        self.assertIn(b'original_result=-5 retained; Sony_entry_not_executed=1', self.lib.test_log())

    def test_successful_posix_read_does_not_run_comparison(self):
        size = c.c_size_t(0)
        self.assertEqual(self.lib.test_dependency(os.fsencode(self.path), self.buffer,
                         len(self.data), c.byref(size)), 0)
        self.assertEqual(size.value, len(self.data))
        self.assertEqual(self.lib.test_reads(), 0)
        self.assertEqual(self.lib.test_closes(), 0)
        self.assertIn(f'POPS_READ size_low={len(self.data)} size_high=0 capacity={len(self.data)}'.encode(),
                      self.lib.test_log())

    def test_positive_posix_close_ignores_stale_errno(self):
        self.lib.test_reset(9, 0)
        size = c.c_size_t(0)
        self.assertEqual(self.lib.test_dependency(os.fsencode(self.path), self.buffer,
                         len(self.data), c.byref(size)), 0)
        self.assertEqual(size.value, len(self.data))
        self.assertEqual(self.buffer.raw[:len(self.data)], self.data)
        self.assertEqual(self.lib.test_closes(), 0)
        self.assertIn(b'POPS_READ close_result=3', self.lib.test_log())
        self.assertNotIn(b'POPS_READ_COMPARE', self.lib.test_log())

    def test_negative_posix_close_retains_error_after_comparison(self):
        for mode, error in ((10, errno.EACCES), (11, errno.EIO)):
            with self.subTest(mode=mode):
                self.lib.test_reset(mode, 0)
                size = c.c_size_t(0x1234)
                self.assertEqual(self.lib.test_dependency(os.fsencode(self.path), self.buffer,
                                 len(self.data), c.byref(size)), -error)
                self.assertEqual(size.value, 0x1234)
                self.assertIn(b'POPS_READ_FAIL stage=close', self.lib.test_log())
                self.assertIn(b'POPS_XIO complete', self.lib.test_log())
                self.assertIn(f'original_result={-error} retained'.encode(), self.lib.test_log())


if __name__ == '__main__':
    unittest.main()
