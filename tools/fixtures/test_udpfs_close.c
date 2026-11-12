#include <assert.h>
#include <stdio.h>
#include <string.h>
#define FEATURE_UDPFS_IOMAN
#include "../../launcher/iop/udpfs/udpfs/src/udpfs_core.c"
static int response_size=8, response_error, response_type=UDPFS_MSG_CLOSE_REPLY;
static int sends;
udprdma_socket_t *udprdma_create(uint16_t port,uint16_t service) { (void)port;(void)service;return (void *)1; }
void udprdma_destroy(udprdma_socket_t *s) { (void)s; }
int udprdma_discover(udprdma_socket_t *s,uint32_t timeout) { (void)s;(void)timeout;return 0; }
int udprdma_is_connected(udprdma_socket_t *s) { return s!=NULL; }
uint32_t udprdma_get_peer_ip(udprdma_socket_t *s) { (void)s;return 0; }
void udprdma_set_rx_buffer(udprdma_socket_t *s,void *buffer,uint32_t size) { (void)s;(void)buffer;(void)size; }
void udprdma_set_rx_app_header(udprdma_socket_t *s,void *buffer,uint32_t size) { (void)s;(void)buffer;(void)size; }
int udprdma_send(udprdma_socket_t *s,const void *p,uint32_t n) { (void)s;(void)p;(void)n;++sends;return 0; }
int udprdma_send_ll(udprdma_socket_t *s,const void *h,uint32_t hn,const void *p,uint32_t n) {
  (void)s;(void)h;(void)hn;(void)p;(void)n;return 0;
}
int udprdma_recv(udprdma_socket_t *s,void *buffer,uint32_t size,uint32_t timeout) {
  (void)s;(void)timeout;
  udpfs_msg_close_reply_t reply;memset(&reply,0,sizeof(reply));
  reply.msg_type=response_type;reply.result=response_error;
  assert(size==sizeof(reply));memcpy(buffer,&reply,sizeof(reply));return response_size;
}
int main(void) {
  g_socket=(void *)1;
  assert(udpfs_core_close(42)==0);
  response_error=-EACCES;assert(udpfs_core_close(42)==-EACCES);
  response_error=0;response_size=-1;assert(udpfs_core_close(42)==-EIO);
  response_size=4;assert(udpfs_core_close(42)==-EIO);
  response_size=8;response_type=UDPFS_MSG_OPEN_REPLY;assert(udpfs_core_close(42)==-EIO);
  g_socket=NULL;int before=sends;assert(udpfs_core_close(42)==-EIO&&before==sends);
  puts("UDPFS close failure, short reply and wrong reply PASS");return 0;
}
