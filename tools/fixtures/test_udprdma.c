/* Execute the actual transport with scripted IOP/network delivery. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../launcher/iop/udpfs/udpfs/src/udprdma.c"

static uint32_t flags;
static int sequence[16], count, cursor, sends, alarms, binds;
static uint8_t frame[80];
static udp_socket_t binding;
static unsigned int (*alarm_cb)(void *);
static void *alarm_arg;
static void script(const int *values, int n) {
  memcpy(sequence,values,n*sizeof(*values)); count=n; cursor=0;
}
int CreateEventFlag(iop_event_t *e) { flags=e->bits; return 1; }
int DeleteEventFlag(int id) { (void)id; return 0; }
int SetEventFlag(int id,uint32_t bits) { (void)id; flags|=bits; return 0; }
int iSetEventFlag(int id,uint32_t bits) { return SetEventFlag(id,bits); }
int ClearEventFlag(int id,uint32_t bits) { (void)id; flags&=bits; return 0; }
int WaitEventFlag(int id,uint32_t bits,int mode,uint32_t *out) {
  (void)id;
  while (!(flags&bits)) {
    assert(cursor<count);
    int ev=sequence[cursor++];
    memset(frame,0,sizeof(frame));
    if (ev == -1) { assert(alarm_cb); alarm_cb(alarm_arg); }
    else if (ev == -2) {
      udprdma_pkt_disc_t *p=(void *)frame;
      p->hdr.packet_type=UDPRDMA_PT_INFORM;
      p->disc.service_id=UDPRDMA_SVC_UDPFS;
      binding.handler(&binding,binding.handler_arg,frame,44);
    } else {
      udprdma_pkt_data_t *p=(void *)frame;
      p->hdr.packet_type=UDPRDMA_PT_DATA;
      p->data.flags=UDPRDMA_DF_ACK;
      p->data.seq_nr_ack=ev;
      binding.handler(&binding,binding.handler_arg,frame,44);
    }
  }
  *out=flags;
  if (mode&WEF_CLEAR) flags=0;
  return 0;
}
void USec2SysClock(uint32_t us,iop_sys_clock_t *c) { c->lo=us;c->hi=0; }
int SetAlarm(iop_sys_clock_t *c,unsigned int (*cb)(void *),void *a) {
  (void)c; alarm_cb=cb;alarm_arg=a;++alarms;return 0;
}
int CancelAlarm(unsigned int (*cb)(void *),void *a) {
  (void)cb;(void)a;alarm_cb=NULL;return 0;
}
int DelayThread(int us) { (void)us; return 0; }
void smap_fifo_read(uint16_t off,void *dst,uint32_t n) { memcpy(dst,frame+off,n); }
udp_socket_t *udp_bind(uint16_t port,udp_port_handler handler,void *arg) {
  ++binds; binding.port_src=port;binding.handler=handler;binding.handler_arg=arg;return &binding;
}
void udp_unbind(udp_socket_t *socket) { assert(socket==&binding);binding.handler=NULL; }
void udp_packet_init(udp_packet_t *p,uint32_t ip,uint16_t port) { (void)ip;p->udp.port_dst=htons(port); }
int udp_packet_send_ll(udp_socket_t *s,udp_packet_t *p,uint16_t h,const void *d,uint16_t n) {
  (void)s;(void)p;(void)h;(void)d;if(n)++sends;return 0;
}
int main(void) {
  uint32_t payload=0;
  udprdma_socket_t *s=udprdma_create(0,UDPRDMA_SVC_UDPFS); assert(s);
  int inform[]={-2};script(inform,1);assert(udprdma_discover(s,100)==0);
  assert(s->tx_seq_nr==0 && s->tx_seq_nr_acked==4095);
  int ack[]={4095,0};script(ack,2);sends=alarms=0;
  assert(udprdma_send(s,&payload,4)==0);assert(cursor==2&&sends==1&&alarms==1);
  int stale_timeout[]={0,-1,1};script(stale_timeout,3);sends=alarms=0;
  assert(udprdma_send_ll(s,&payload,4,&payload,4)==0);assert(cursor==3&&sends==2&&alarms==2);
  s->tx_seq_nr=4095;int wrap[]={4094,4095};script(wrap,2);
  assert(udprdma_send(s,&payload,4)==0);assert(cursor==2&&s->tx_seq_nr==0);
  s->rx_seq_nr_expected=99;s->rx_window_count=4;s->rx_nack_sent=1;
  s->rx_buffer=&payload;s->rx_hdr_buffer=&payload;s->state=STATE_DISCONNECTED;
  script(inform,1);assert(udprdma_discover(s,100)==0);
  assert(s->tx_seq_nr==0&&s->tx_seq_nr_acked==4095&&s->rx_seq_nr_expected==0);
  assert(!s->rx_buffer&&!s->rx_hdr_buffer&&!s->rx_nack_sent&&!s->rx_window_count&&binds==1);
  udprdma_destroy(s);assert(!binding.handler);
  puts("UDPFS stale ACK, retry, wrap and rediscovery PASS");return 0;
}
