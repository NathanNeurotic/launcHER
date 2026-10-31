#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include "network_config.h"
#include "smb_open_contract.h"

int main(void) {
    LauncherSmbConfig c;
    const char *guest = "192.168.1.100 PS2SMB\n\n\n";
    assert(launcher_parse_smb_config(guest, strlen(guest), &c));
    assert(!strcmp(c.server,"192.168.1.100") && c.port == 445);
    assert(!strcmp(c.share,"PS2SMB") && !c.user[0] && !c.password[0]);
    const char *auth = "192.168.1.100:1445 Share Name\r\ntest user\r\npass word\r\n";
    assert(launcher_parse_smb_config(auth, strlen(auth), &c));
    assert(c.port == 1445 && !strcmp(c.share,"Share Name"));
    assert(!strcmp(c.user,"test user") && !strcmp(c.password,"pass word"));
    const char *decimal="192.168.001.010 PS2SMB\n\n\n";
    assert(launcher_parse_smb_config(decimal,strlen(decimal),&c));
    assert(!strcmp(c.server,"192.168.1.10"));
    const char *bad[] = {"192.168.1.999 SHARE\n", "192.168.1.1:0 SHARE\n",
      "192.168.1.1:65536 SHARE\n", "host SHARE\n", "192.168.1.1 /SHARE\n",
      "192.168.1.1\n", "192.168.1.1 SHARE\nu\np\nextra", "192.168.1.1: SHARE\n"};
    for (unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);++i)
      assert(!launcher_parse_smb_config(bad[i],strlen(bad[i]),&c));
    char longline[800]; memset(longline,'x',sizeof(longline));
    assert(!launcher_parse_smb_config(longline,sizeof(longline),&c));
    assert(!launcher_parse_smb_config(guest,strlen(guest)+1,&c));
    const char *ip = "192.168.1.10 255.255.255.0 192.168.1.1\r\n";
    char packed[48]; size_t n = 0;
    assert(launcher_parse_tcpip_config(ip,strlen(ip),packed,&n));
    assert(n == sizeof("192.168.1.10\0" "255.255.255.0\0" "192.168.1.1") );
    assert(!memcmp(packed,"192.168.1.10\0" "255.255.255.0\0" "192.168.1.1",n));
    assert(!launcher_parse_tcpip_config(ip,12,packed,&n));
    assert(!launcher_parse_tcpip_config("1.1.1.1 2.2.2.2 3.3.3.3 junk",28,packed,&n));
    assert(launcher_smb_nt_disposition(O_WRONLY|O_CREAT|O_EXCL|O_TRUNC) == 2);
    assert(launcher_smb_legacy_disposition(O_WRONLY|O_CREAT|O_EXCL|O_TRUNC) == 0x10);
    assert(launcher_smb_nt_disposition(O_RDONLY) == 1);
    assert(launcher_smb_nt_disposition(O_CREAT) == 3);
    assert(launcher_smb_nt_disposition(O_CREAT|O_TRUNC) == 5);
    assert(launcher_smb_nt_disposition(O_TRUNC) == 4);
    assert(launcher_smb_legacy_disposition(O_CREAT|O_TRUNC) == 0x12);
    puts("Network configuration and atomic SMB creation PASS");
    return 0;
}
