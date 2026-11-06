# LZMA decoder provenance

These five files are unmodified upstream 7-Zip C decoder sources. Their source
headers declare them public domain, by Igor Pavlov. No POPStarter decoder code
or Sony dependency is included.

Upstream: https://github.com/ip7z/7zip/tree/e5431fa6f5505e385c6f9367260717e9c47dc2ee/C

Pinned release: 24.09, commit `e5431fa6f5505e385c6f9367260717e9c47dc2ee`.

| File | SHA256 |
| --- | --- |
| 7zTypes.h | 5de943c886d5d7bbcf16203e9b292a9e7be327b43fe3dfd9f4ad07d6d0870ef6 |
| Compiler.h | 959dac87ac7109502f6467e910d0722b932176e243153bf8c663479aa8c29b20 |
| LzmaDec.c | b9ca2b8707400347c75d6fef288d1354a3b4cf93e8da42f26207b8bd4c4d5e59 |
| LzmaDec.h | 3aaf07b4ae4173a2d103179455dc7089b5ddbc7fc3db3c0e40964a7499c69266 |
| Precomp.h | fea249c753dfbbdd69d9397e91497205452b784279f70cad4658dc567cd2f85f |

`common/src/pops_pak.c` supplies the PAK framing and allocator. It uses the
one-call decoder, which allocates probabilities but uses the caller's output
as the dictionary, avoiding an additional 8 MiB dictionary allocation.
