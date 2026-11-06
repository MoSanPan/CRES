#pragma once
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
 unsigned int eax,ebx,ecx,edx;
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
