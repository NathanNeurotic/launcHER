# Embedded SMBv1 client

Source: ps2dev/ps2sdk `iop/network/smbman/src` and
`common/include/ps2smb.h`, commit
`3304cd864748ce40b1ff9fb41cc5a700f5e573a0`.
Upstream: https://github.com/ps2dev/ps2sdk/tree/3304cd864748ce40b1ff9fb41cc5a700f5e573a0/iop/network/smbman

The source is retained here because the installed SDK client does not honor
`O_CREAT | O_EXCL`, which launcHER's VMC creation needs to preserve a card
created concurrently. `smb_open_contract.h` selects atomic FILE_CREATE or
the equivalent legacy OpenAndX action. Missing-file and name-collision
statuses map to ENOENT/EEXIST. `_start` reports driver registration failure.
Other protocol/authentication code retains its upstream behavior.

Local changes by the launcHER contributors, with ChatGPT/OpenAI assistance,
2026-10-15. The Academic Free License 3.0 applies to the SMB source;
SDK glue also retains AFL 2.0 notices. Eric Young's DES implementation
retains its original SSLeay terms and attribution. This product includes
software developed by Eric Young (eay@mincom.oz.au).

Build with the same SDK as launcHER. The original ABI header is shared
between the EE session controller and this IOP module. Host regression
tests execute the creation-flag helper and the production session controller
with scripted devctl responses. This is not physical server acceptance.
