"""Read only relevant enum labels/defaults from standard IL2CPP v31 metadata."""
from pathlib import Path
import json
import struct
import tempfile

path = Path(r"D:\SteamLibrary\steamapps\common\UmamusumePrettyDerby\UmamusumePrettyDerby_Data\il2cpp_data\Metadata\global-metadata.dat")
b = path.read_bytes()
def table(i, size):
    at, length = struct.unpack_from("<II", b, 8+i*8)
    assert length % size == 0
    return at, length//size
s, sn = table(2,1)
t, tn = table(19,88)
f, fn = table(11,12)
d, dn = table(7,12)
data, _ = table(8,1)
def name(i):
    return b[s+i:b.index(0,s+i)].decode()
defaults = {struct.unpack_from('<iii',b,d+i*12)[0]:struct.unpack_from('<iii',b,d+i*12)[2] for i in range(dn)}
def number(at):
    p = data+at
    first=b[p]
    if first < 0x80:
        u=first
    elif first<0xc0:
        u=((first&0x3f)<<8)|b[p+1]
    elif first<0xe0:
        u=((first&0x1f)<<24)|(b[p+1]<<16)|(b[p+2]<<8)|b[p+3]
    elif first==0xf0:
        u=struct.unpack_from('<I',b,p+1)[0]
    elif first==0xff:
        return -1
    else:
        return 'raw:'+b[p:p+6].hex()
    return -(u>>1)-1 if u&1 else u>>1
result=[]
for i in range(tn):
    at=t+i*88
    type_name, ns=[name(v) for v in struct.unpack_from('<II',b,at)]
    if not any(x in type_name.lower() for x in ['abilityvalue','abilitytime','skillability','coursetype','courseparamtype']) and type_name not in {'RaceManagerSimulate','HorseRaceInfoSimulate'}:
        continue
    field_start=struct.unpack_from('<i',b,at+32)[0]
    nfields=struct.unpack_from('<H',b,at+68)[0]
    fields=[]
    for j in range(nfields):
        fi=field_start+j
        field_name=name(struct.unpack_from('<I',b,f+fi*12)[0])
        enum = bool(struct.unpack_from('<I',b,at+80)[0] & 2)
        value = number(defaults[fi]) if fi in defaults and enum else None
        if fi in defaults and not enum:
            offset=data+defaults[fi]
            value={'raw':b[offset:offset+4].hex(),'float32':struct.unpack_from('<f',b,offset)[0]}
        fields.append({'name':field_name,'value':value})
    result.append({'name':type_name,'namespace':ns,'fields':fields})
out=Path(tempfile.gettempdir())/'uma-race-lab-build25384634/skill-enums.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
for item in result:
    if item['fields'] and len(item['fields'])<80:
        print(item['namespace']+'.'+item['name'],item['fields'])
