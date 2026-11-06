#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <string>
#include <unordered_map>
#include <vector>
#include <stdexcept>
#if (defined(__x86_64__) || defined(__i386__)) && (defined(__GNUC__) || defined(__clang__))
#include <wmmintrin.h>
#include <cpuid.h>
#define CMS_X86_DISPATCH 1
#endif
using namespace std;
static uint32_t slowmul(uint32_t a,uint32_t b){
 uint32_t z=0;for(int i=0;i<32;i++){if(b&1)z^=a;b>>=1;bool hi=a>>31;a<<=1;if(hi)a^=0x8d;}return z;
}
#ifdef CMS_X86_DISPATCH
__attribute__((target("pclmul,sse2"))) static uint64_t clmul(uint64_t a,uint64_t b){
 auto z=_mm_clmulepi64_si128(_mm_set_epi64x(0,a),_mm_set_epi64x(0,b),0);
 return (uint64_t)_mm_cvtsi128_si64(z);
}
__attribute__((target("pclmul,sse2"))) static uint32_t fastmul(uint32_t a,uint32_t b){
 uint64_t z=clmul(a,b), t=clmul(z>>32,0x8d);
 return uint32_t(z)^uint32_t(t)^uint32_t(clmul(t>>32,0x8d));
}
#endif
using Mul=uint32_t(*)(uint32_t,uint32_t);
static Mul choose_mul(){
#if defined(CMS_X86_DISPATCH) && !defined(CMS_FORCE_PORTABLE)
 unsigned int eax=0,ebx=0,ecx=0,edx=0;
 if(__get_cpuid(1,&eax,&ebx,&ecx,&edx)&&(ecx&(1u<<1)))return fastmul;
#endif
 return slowmul;
}
static uint32_t mul(uint32_t a,uint32_t b){static Mul f=choose_mul();return f(a,b);}
struct Hash{
 uint32_t a[5];
 uint32_t operator()(uint32_t x)const{uint32_t y=a[4];for(int i=3;i>=0;i--)y=mul(y,x)^a[i];return y;}
};
struct Entry{uint64_t key,count;};
struct Dict{
 size_t cap;vector<Entry>a;
 Dict(size_t k):cap(k){a.reserve(k);}
 auto at(uint32_t x){return lower_bound(a.begin(),a.end(),x,[](const Entry&e,uint32_t q){return e.key<q;});}
 bool add(uint32_t x){auto i=at(x);if(i!=a.end()&&i->key==x){i->count++;return true;}if(a.size()<cap){a.insert(i,{x,1});return true;}return false;}
 uint64_t get(uint32_t x){auto i=at(x);return i!=a.end()&&i->key==x?i->count:0;}
 uint64_t mass()const{uint64_t s=0;for(auto&e:a)s+=e.count;return s;}
 void mgadd(uint32_t x){if(add(x))return;for(auto&e:a)e.count--;a.erase(remove_if(a.begin(),a.end(),[](const Entry&e){return e.count==0;}),a.end());}
};
static long double clip(long double x,long double hi){return max((long double)0,min(x,hi));}
static long double alpha(long double R,long double v,long double m){
 if(R==0||v<=1||m==0)return 0;
 long double a=floor(R/v),s=R-a*v,F=(v-s)*a*a+s*(a+1)*(a+1);
 long double c=max((long double)0,1-R*R/(v*F));return m*c/(v-1+m*c);
}
int main(int argc,char**argv){
 try {
 if(argc<5||argc>9){cerr<<"usage: experiment stream.bin keybits payload_words repetitions [rows=5] [absent_samples=131072] [rep_start=0] [residual_width=w0/2]\n";return 1;}
 string file=argv[1];int bits=stoi(argv[2]),M=stoi(argv[3]),reps=stoi(argv[4]);
 const int d=argc>5?stoi(argv[5]):5;
 const uint64_t requested_absent=argc>6?stoull(argv[6]):131072;
 const int rep_start=argc>7?stoi(argv[7]):0;
 if((bits!=16&&bits!=32)||M<1||reps<1||d<1||requested_absent<2||rep_start<0)throw runtime_error("invalid arguments");
 mt19937_64 verify(117);for(int i=0;i<10000;i++){uint32_t a=verify(),b=verify();assert(mul(a,b)==slowmul(a,b));}
 ifstream in(file,ios::binary);if(!in)throw runtime_error("cannot open input");
 vector<uint32_t>x;unsigned char bytes[4];while(in.read((char*)bytes,4)){
  uint32_t val=uint32_t(bytes[0])|(uint32_t(bytes[1])<<8)|(uint32_t(bytes[2])<<16)|(uint32_t(bytes[3])<<24);
  if(bits==16&&val>=65536)throw runtime_error("key outside declared universe");x.push_back(val);
 }
 if(in.gcount()!=0)throw runtime_error("input size is not a multiple of four bytes");
 const int w0=M/d,w=argc>8?stoi(argv[8]):w0/2,k=(M-d*w)/2,mgk=M/2,T=x.size();
 if(w0<4||(w0&(w0-1))||T<1||k<0||w<2||w>w0||(w&(w-1)))throw runtime_error("need nonempty input and power-of-two baseline width at least four and valid residual width");
 long double u=ldexp((long double)1,bits);
 unordered_map<uint32_t,uint64_t>f;for(auto q:x)f[q]++;
 vector<uint32_t>present;long double F2=0;for(auto [q,v]:f){present.push_back(q);F2+=(long double)v*v;}sort(present.begin(),present.end());
 const vector<string>names={"zero","constant","CMS_min","CU_min","CMS_mean_plus","CS_mean_plus","CS_median_plus","CMS_shrink","CS_shrink","dictionary_CMS_raw","proposed_affine","proposed_projected","Misra_Gries","CMM_mean"};
 cout<<"source,bits,T,K,payload_words,d,w0,w,k,rep,algorithm,mse,present_mse,absent_mse,absent_samples,query_mc_se,frequency_weighted_mse\n";
 for(int rep=rep_start;rep<rep_start+reps;rep++){
  mt19937_64 rng(2026102600ULL+rep);vector<Hash>h(d);for(auto&hr:h)for(auto&a:hr.a)a=uint32_t(rng());
  vector<int64_t>cms(d*w0,0),cu(d*w0,0),cs(d*w0,0),res(d*w,0);
  Dict dict(k),mg(mgk);uint64_t R=0;
  for(auto q:x){
   bool saved=dict.add(q);mg.mgadd(q);if(!saved)R++;
   vector<uint32_t>hv(d);int64_t mincu=INT64_MAX;
   for(int r=0;r<d;r++){hv[r]=h[r](q);auto b=hv[r]&(w0-1);cms[r*w0+b]++;cs[r*w0+b]+=(hv[r]>>31)?-1:1;mincu=min(mincu,cu[r*w0+b]);if(!saved)res[r*w+(hv[r]&(w-1))]++;}
   for(int r=0;r<d;r++){auto &a=cu[r*w0+(hv[r]&(w0-1))];if(a==mincu)a++;}
  }
  long double v=u-dict.a.size(),b=R/v,al=alpha(R,v,d*(w-1));
  long double acms=alpha(T,u,d*(w0-1)),acs=alpha(T,u,d*w0),bp=T/u;
  array<long double,14>sp{},sa{},saa{},sw{};
  auto query=[&](uint32_t q,uint64_t truth,bool ispresent){
   vector<int64_t>csy(d);vector<long double>cmy(d);long double sumcms=0,sumcs=0,sumres=0;int64_t mincms=INT64_MAX,mincu=INT64_MAX,minres=INT64_MAX;
   for(int r=0;r<d;r++){
    uint32_t hv=h[r](q),b0=hv&(w0-1),br=hv&(w-1);int sign=(hv>>31)?-1:1;
    mincms=min(mincms,cms[r*w0+b0]);mincu=min(mincu,cu[r*w0+b0]);minres=min(minres,res[r*w+br]);
    cmy[r]=((long double)w0*cms[r*w0+b0]-T)/(w0-1);sumcms+=cms[r*w0+b0];sumres+=res[r*w+br];csy[r]=sign*cs[r*w0+b0];sumcs+=csy[r];
   }
   sort(csy.begin(),csy.end());sort(cmy.begin(),cmy.end());
   long double A=(w0*sumcms-d*T)/(d*(w0-1)),B=sumcs/d,Ar=(w*sumres-d*R)/(d*(w-1));
   uint64_t count=dict.get(q);
   long double aff=count?count:b+al*(Ar-b);
   array<long double,14>est={0,bp,(long double)mincms,(long double)mincu,clip(A,T),clip(B,T),clip(d%2?(long double)csy[d/2]:((long double)csy[d/2-1]+csy[d/2])/2,T),clip(bp+acms*(A-bp),mincms),clip(bp+acs*(B-bp),T),count?(long double)count:clip(Ar,minres),aff,count?(long double)count:clip(aff,minres),(long double)mg.get(q),clip(d%2?cmy[d/2]:(cmy[d/2-1]+cmy[d/2])/2,mincms)};
   for(int j=0;j<14;j++){long double er=est[j]-truth,e=er*er;if(ispresent){sp[j]+=e;sw[j]+=e*truth;}else {sa[j]+=e;saa[j]+=e*e;}}
  };
  for(auto q:present)query(q,f[q],true);
  uint64_t N=0;
  if(bits==16){for(uint32_t q=0;q<65536;q++)if(!f.count(q)){query(q,0,false);N++;}}
  else{
   mt19937_64 qrng(7740041ULL+rep);
   while(N<requested_absent){uint32_t q=uint32_t(qrng());if(!f.count(q)){query(q,0,false);N++;}}
  }
  for(int j=0;j<14;j++){
   long double ea=N?sa[j]/N:0,mse=sp[j]/u+(1-(long double)f.size()/u)*ea;
   long double vv=N>1?max((long double)0,(saa[j]-sa[j]*sa[j]/N)/(N-1)):0;
   long double se=bits==16?0:(1-(long double)f.size()/u)*sqrt(vv/N);
   cout<<setprecision(18)<<file<<','<<bits<<','<<T<<','<<f.size()<<','<<M<<','<<d<<','<<w0<<','<<w<<','<<k<<','<<rep<<','<<names[j]<<','<<double(mse)<<','<<double(sp[j]/f.size())<<','<<double(ea)<<','<<N<<','<<double(se)<<','<<double(sw[j]/T)<<'\n';
  }
 }
 return 0;
 }catch(const exception& e){cerr<<"error: "<<e.what()<<"\n";return 2;}
}
