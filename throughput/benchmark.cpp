#include "original_components.hpp"
#include <chrono>
#include <numeric>
#include <type_traits>

using Clock = std::chrono::steady_clock;
static volatile long double sink = 0;
static constexpr int D = 5;
static constexpr long double U = 4294967296.0L;

static vector<Hash> make_hashes(int rep) {
    mt19937_64 rng(2026102600ULL + rep);
    vector<Hash> h(D);
    for (auto &hr : h) for (auto &a : hr.a) a = uint32_t(rng());
    return h;
}

template<bool Signed> struct Sketch {
    vector<Hash> h;
    vector<int64_t> table;
    int width;
    uint64_t n = 0;
    long double base = 0, shrink = 0;
    Sketch(int M, int rep):h(make_hashes(rep)),table(M,0),width(M/D) {}
    void add(uint32_t q) {
        ++n;
        for(int r=0;r<D;++r) {
            auto hv=h[r](q);
            table[r*width+(hv&(width-1))] += Signed ? ((hv>>31)?-1:1) : 1;
        }
    }
    void finalize() {
        base=n/U;
        shrink=alpha(n,U,D*(Signed?width:width-1));
    }
    long double query(uint32_t q) {
        long double sum=0; int64_t hi=INT64_MAX;
        for(int r=0;r<D;++r) {
            auto hv=h[r](q); auto v=table[r*width+(hv&(width-1))];
            sum+=Signed ? ((hv>>31)?-v:v) : v;
            if constexpr(!Signed) hi=min(hi,v);
        }
        long double a=Signed ? sum/D : (width*sum-D*n)/(D*(width-1));
        return clip(base+shrink*(a-base),Signed ? (long double)n : (long double)hi);
    }
    size_t bytes() const {return sizeof(*this)+h.capacity()*sizeof(Hash)+table.capacity()*sizeof(int64_t);}
};

struct CMM : Sketch<false> {
    CMM(int M,int rep):Sketch<false>(M,rep){}
    long double query(uint32_t q) {
        array<long double,D> row{};int64_t hi=INT64_MAX;
        for(int r=0;r<D;r++){auto c=table[r*width+(h[r](q)&(width-1))];row[r]=(width*(long double)c-n)/(width-1);hi=min(hi,c);}
        sort(row.begin(),row.end());return clip(row[D/2],hi);
    }
};

struct Hybrid {
    vector<Hash> h;
    vector<int64_t> table;
    Dict dict;
    int width;
    uint64_t residual=0;
    long double base=0,shrink=0;
    Hybrid(int M,int rep):h(make_hashes(rep)),table(D*((M/D)/2),0),dict((M-D*((M/D)/2))/2),width((M/D)/2) {}
    void add(uint32_t q) {
        if(dict.add(q))return;
        ++residual;
        for(int r=0;r<D;++r)table[r*width+(h[r](q)&(width-1))]++;
    }
    void finalize() {
        long double v=U-dict.a.size();base=residual/v;shrink=alpha(residual,v,D*(width-1));
    }
    long double query(uint32_t q) {
        auto count=dict.get(q);if(count)return count;
        long double sum=0;int64_t hi=INT64_MAX;
        for(int r=0;r<D;++r){auto v=table[r*width+(h[r](q)&(width-1))];sum+=v;hi=min(hi,v);}
        auto a=(width*sum-D*residual)/(D*(width-1));
        return clip(base+shrink*(a-base),hi);
    }
    size_t bytes()const{return sizeof(*this)+h.capacity()*sizeof(Hash)+table.capacity()*sizeof(int64_t)+dict.a.capacity()*sizeof(Entry);}
};

struct MG {
    Dict dict;
    MG(int M,int):dict(M/2){}
    void add(uint32_t q){dict.mgadd(q);}
    void finalize(){}
    long double query(uint32_t q){return dict.get(q);}
    size_t bytes()const{return sizeof(*this)+dict.a.capacity()*sizeof(Entry);}
};

// Independently maintain the original simultaneous evaluator's four relevant states.
static void check_correctness() {
    mt19937_64 verify(117);
    for(int i=0;i<10000;i++){uint32_t a=verify(),b=verify();if(mul(a,b)!=slowmul(a,b))throw runtime_error("GF check failed");}
    const int M=1280,w0=M/D,w=w0/2,k=(M-D*w)/2,T=8192;
    auto h=make_hashes(0);vector<int64_t>cms(D*w0),cs(D*w0),res(D*w);Dict dict(k),mg(M/2);uint64_t R=0;
    Sketch<false> a(M,0);Sketch<true>b(M,0);Hybrid c(M,0);MG e(M,0);CMM cm(M,0);
    vector<uint32_t>x;mt19937_64 rng(1234567);
    for(int i=0;i<T;i++){uint32_t q=uint32_t(rng()%2048);x.push_back(q);bool saved=dict.add(q);mg.mgadd(q);if(!saved)++R;for(int r=0;r<D;r++){auto hv=h[r](q);cms[r*w0+(hv&(w0-1))]++;cs[r*w0+(hv&(w0-1))]+=(hv>>31)?-1:1;if(!saved)res[r*w+(hv&(w-1))]++;}a.add(q);b.add(q);c.add(q);e.add(q);cm.add(q);}
    a.finalize();b.finalize();c.finalize();e.finalize();
    if(a.table!=cms||b.table!=cs||c.table!=res||c.residual!=R)throw runtime_error("state mismatch");
    auto bp=T/U,acms=alpha(T,U,D*(w0-1)),acs=alpha(T,U,D*w0),v=U-dict.a.size(),br=R/v,ar=alpha(R,v,D*(w-1));
    for(int j=0;j<8192;j++){
        uint32_t q=j<4096?uint32_t(j):uint32_t(rng());long double sumcms=0,sumcs=0,sumres=0;int64_t mincms=INT64_MAX,minres=INT64_MAX;
        array<long double,D> corrected{};
        for(int r=0;r<D;r++){auto hv=h[r](q);auto yc=cms[r*w0+(hv&(w0-1))],yr=res[r*w+(hv&(w-1))];sumcms+=yc;sumres+=yr;sumcs+=((hv>>31)?-1:1)*cs[r*w0+(hv&(w0-1))];mincms=min(mincms,yc);minres=min(minres,yr);corrected[r]=(w0*(long double)yc-T)/(w0-1);}
        sort(corrected.begin(),corrected.end());
        auto A=(w0*sumcms-D*T)/(D*(w0-1)),B=sumcs/D,Ar=(w*sumres-D*R)/(D*(w-1));auto count=dict.get(q);
        array<long double,5>ref={clip(bp+acms*(A-bp),mincms),clip(bp+acs*(B-bp),T),count?(long double)count:clip(br+ar*(Ar-br),minres),(long double)mg.get(q),clip(corrected[D/2],mincms)};
        array<long double,5>actual={a.query(q),b.query(q),c.query(q),e.query(q),cm.query(q)};
        for(int z=0;z<5;z++)if(!isfinite(ref[z])||!isfinite(actual[z])||fabsl(ref[z]-actual[z])>1e-15L*max(1.0L,fabsl(ref[z])))throw runtime_error("query mismatch");
    }
}

template<class State> static void run(const string& name,int M,int rep,bool warmup,const vector<uint32_t>&x,const vector<uint32_t>&present,const vector<uint32_t>&uniform) {
    State state(M,rep);
    auto t0=Clock::now();for(auto q:x)state.add(q);auto t1=Clock::now();
    state.finalize();
    long double check1=0,check2=0;
    auto t2=Clock::now();for(auto q:present)check1+=state.query(q);auto t3=Clock::now();
    auto t4=Clock::now();for(auto q:uniform)check2+=state.query(q);auto t5=Clock::now();
    sink=check1+check2;
    auto sec=[](auto a,auto b){return chrono::duration<double>(b-a).count();};
    cout<<setprecision(18)<<name<<','<<M<<','<<x.size()<<','<<present.size()<<','<<rep<<','<<warmup<<','<<sec(t0,t1)<<','<<sec(t2,t3)<<','<<sec(t4,t5)<<','<<8*M<<','<<state.bytes()<<','<<(double)check1<<','<<(double)check2<<'\n';
}

int main(int argc,char**argv) {
  try{
    check_correctness();
    if(argc>1&&string(argv[1])=="--check"){cout<<"PASS: GF arithmetic, simultaneous-state equivalence and 40960 query comparisons\n";return 0;}
    size_t T=argc>1?stoull(argv[1]):1048576,Q=argc>2?stoull(argv[2]):262144;int reps=argc>3?stoi(argv[3]):5;
    vector<uint32_t>x(T),present(Q),uniform(Q);mt19937_64 input(2026102901ULL),queries(2026102902ULL);
    for(auto&q:x)q=uint32_t(input());for(size_t i=0;i<Q;i++){present[i]=x[queries()%T];uniform[i]=uint32_t(queries());}
    cout<<"algorithm,payload_words,T,queries,rep,warmup,update_seconds,present_query_seconds,uniform_query_seconds,payload_bytes,state_and_capacity_bytes,present_checksum,uniform_checksum\n";
    mt19937_64 order_rng(2026102903ULL);
    for(int rep=-1;rep<reps;rep++)for(int M:{1280,5120}){
        vector<int>order={0,1,2,3,4};shuffle(order.begin(),order.end(),order_rng);
        for(int a:order)switch(a){case 0:run<Sketch<false>>("CMS_shrink",M,max(0,rep),rep<0,x,present,uniform);break;case 1:run<Sketch<true>>("CS_shrink",M,max(0,rep),rep<0,x,present,uniform);break;case 2:run<Hybrid>("proposed_projected",M,max(0,rep),rep<0,x,present,uniform);break;case 3:run<MG>("Misra_Gries",M,max(0,rep),rep<0,x,present,uniform);break;case 4:run<CMM>("CMM_mean",M,max(0,rep),rep<0,x,present,uniform);break;}
    }
    return 0;
  }catch(const exception&e){cerr<<e.what()<<'\n';return 1;}
}
