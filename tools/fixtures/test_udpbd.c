#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../../launcher/iop/udpfs/udpbd/src/udpbd.c"
static uint32_t event;
static uint8_t frame[1600];
static udp_socket_t binding;
int CreateEventFlag(iop_event_t *e) { (void)e;return 1; }
int DeleteEventFlag(int id) { (void)id;return 0; }
int SetEventFlag(int id,uint32_t bits) { (void)id;event|=bits;return 0; }
int iSetEventFlag(int id,uint32_t bits) { return SetEventFlag(id,bits); }
int WaitEventFlag(int id,uint32_t bits,int mode,uint32_t *out) {
  (void)id;(void)bits;(void)mode;*out=event;event=0;return 0;
}
void USec2SysClock(uint32_t us,iop_sys_clock_t *c) { c->lo=us;c->hi=0; }
int SetAlarm(iop_sys_clock_t *c,unsigned int (*cb)(void *),void *a) { (void)c;(void)cb;(void)a;return 0; }
int CancelAlarm(unsigned int (*cb)(void *),void *a) { (void)cb;(void)a;return 0; }
int DelayThread(int us) { (void)us;return 0; }
void bdm_connect_bd(struct block_device *b) { (void)b; }
void bdm_disconnect_bd(struct block_device *b) { (void)b; }
void smap_fifo_read(uint16_t off,void *dst,uint32_t n) { assert(off+n<=sizeof(frame));memcpy(dst,frame+off,n); }
udp_socket_t *udp_bind(uint16_t port,udp_port_handler h,void *a) { (void)port;(void)h;(void)a;return &binding; }
void udp_packet_init(udp_packet_t *p,uint32_t ip,uint16_t port) { (void)p;(void)ip;(void)port; }
int udp_packet_send_ll(udp_socket_t *s,udp_packet_t *p,uint16_t h,const void *d,uint16_t n) {
  (void)s;(void)p;(void)h;(void)d;(void)n;return 0;
}
static void packet(unsigned count,unsigned shift,unsigned remaining) {
  static unsigned char buffer[12];
  union block_type bt;memset(&bt,0,sizeof(bt));bt.block_count=count;bt.block_shift=shift;
  memcpy(frame+0x2c,&bt.bt,4);memset(buffer,0xa5,sizeof(buffer));
  g_buffer=g_buffer_act=buffer;g_read_size=remaining;g_read_cmdpkt=1;event=0;g_errno=0;
  struct SUDPBDv2_Header hdr;memset(&hdr,0,sizeof(hdr));hdr.cmdpkt=1;
  _cmd_read_rdma(&hdr);
  if(!count||shift>7||count>(RDMA_MAX_PAYLOAD>>(shift+2))||(count<<(shift+2))>remaining) {
    assert(event==2&&g_errno==3&&buffer[0]==0xa5);
  } else assert(event==1&&g_read_size==0&&buffer[8]==0xa5);
}
int main(void) {
  packet(2,0,4);packet(0,0,4);packet(1,8,4);packet(1,15,4);packet(0xfffff,7,4);packet(2,0,8);
  struct SUDPBDv2_Header hdr;memset(&hdr,0,sizeof(hdr));
  int32_t result=-5;memcpy(frame+0x2c,&result,4);event=0;_cmd_write_done(&hdr);
  assert(event==2&&g_errno==-5);
  result=0;memcpy(frame+0x2c,&result,4);event=0;_cmd_write_done(&hdr);
  assert(event==1&&g_errno==0);
  puts("UDPBD destination bounds and server write failure PASS");return 0;
}
