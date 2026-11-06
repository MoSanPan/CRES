"""Offline reconstruction of every included experimental input, including models."""
import argparse,hashlib,json,struct,zipfile,zlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 (ROOT/'validation').mkdir(parents=True,exist_ok=True)
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args()
 data=ROOT/'data';manifest=json.loads((data/'provenance/manifest.json').read_text());raw={}
 with zipfile.ZipFile(data/'archives/IBM_trials.zip') as z:
  for item in manifest:
   if not item['name'].startswith('IBM'):continue
   bits=''.join(''.join(z.read(f).decode().split()) for f in item['files'])
   if set(bits)-set('01') or len(bits)%8:raise ValueError('Invalid IBM bit stream')
   b=bytes(int(bits[i:i+8],2) for i in range(0,len(bits),8));raw[item['name']]=b
 archive=(data/'archives/ANU_archive_prefix.bin').read_bytes()
 header=struct.unpack('<IHHHHHIIIHH',archive[:30]);assert header[0]==0x04034b50 and header[3]==8
 start=30+header[-2]+header[-1]
 raw['ANU_public_prefix']=zlib.decompressobj(-15).decompress(archive[start:],1048576)
 files={};expected=json.loads((data/'provenance/input_validation.json').read_text())
 for item in manifest:
  b=raw[item['name']];assert digest(b)==item['raw_sha256'];assert b==(data/'raw'/f"{item['name']}.raw").read_bytes()
  for bits in [16,32]:
   k=bits//8;vals=[int.from_bytes(b[i:i+k],'big') for i in range(0,16384*k,k)]
   name=f"{item['name']}_{bits}.bin";out=struct.pack('<16384I',*vals)
   assert digest(out)==expected[name];files[name]=out
 model=json.loads((data/'provenance/model_sources.json').read_text());rng=np.random.default_rng(model['seed']);n=16384
 iid=rng.integers(0,2**32,n,dtype=np.uint32);sticky=rng.integers(0,2**32,n,dtype=np.uint32)
 keep=rng.random(n)<model['sticky']['beta']
 for i in range(1,n):
  if keep[i]:sticky[i]=sticky[i-1]
 files['model_iid_32.bin']=iid.astype('<u4').tobytes();files['model_sticky_32.bin']=sticky.astype('<u4').tobytes()
 for name,b in files.items():
  target=data/'inputs'/name
  assert b==target.read_bytes(),name+' does not match the included input'
  if a.write:target.write_bytes(b)
 report=dict(passed=True,files={name:digest(b) for name,b in files.items()},public_raw_prefixes_verified=3,model_generator='NumPy PCG64, one generator; IID vector, fresh vector, then Bernoulli keep flags')
 (ROOT/'validation/data_rebuild.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
