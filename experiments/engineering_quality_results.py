"""Generated CI diagnosis data artifact, schema 2.
Synthetic outcomes/costs are declared assumptions.
"""
from ci_diagnosis.artifacts import decode_payload

PAYLOAD_SHA256 = 'e29488dbe41e00abf483dd676332afd737c8cbfeebc8d2e02f8f7b9b77b40f3d'
_ENCODED = (
    'c-qxiYi}#pb^R+-0tIAL<UQ|)nig=Hk4YNDEsVl6i1XM-nqG2-o*Bwk4gdG9Gb2hObzLORZJY2)y2E+wvma}(wa@&xiqxftLl{1;?tWawFw(y5Xm_OWaW@Si'
    'QQpO;iN@8P)S5Z(ZeMR2DfL~(C9_dna$%jXAL;n*YTq8(DNJqO;ri;KAE$MuBXya&scE}$8cqisQf>|u#?wIc+xU-7*Ejdn(Gd2{cqGcF<A<@m@7mI)&?Rcp'
    'KD39`?dm{>et6p5hlyaHLV9S1Q`h|JpBiqO-?hJPY6Q&^K@;}-KF!YH$zvEt%BwqgK=?NFrQKH>&G{pQ;-0aloVrw>X%e0vn;Y&GW0Ez;p~lue(sJPogwyB^'
    'Gp2b?$hO;du=B4&rU9$Rr@JPd4yS#XADY?&&DVe1j#GmhPSwRS^oNEk*GzrGS(8sxj|M`b+Qo}sarV#8mb=9x+%Z*a4T2r&siv-Td8P)}g#+Eyigo?XIjApY'
    'L-U8%KWxLexH!-ouJr4{zuaxN|31<%Znwuje)*f<|HqeKfBE}=+iri;r@4|i|25IaHE;f*sRxbNZd1F<ZMg6HvBhP24Exhuh0XElPRpCrKlH=2L)~7yky0;C'
    '2!D2q%?Dy5y*i(<pTQff3Yg8F@SErJboRp;dtOYx_`w!GgpsdjK7${?%#g?Gh?O^`?e1v+!nz5*2+I@`AG~pHF4Treb>R))Xr=y_ywU3Bh-Q1K4Hx1J5bv+N'
    '5T3nO>o50WY?p3XkirGO=_3q2(tDgRuCIJy!k*8_&)~~}Y6s34;r?bsdO(Rwnm&aVd*Kb+c>gEVXOqBRgq8bDKdgbw+QZ}dd*z!jJe|*Pw`U?vZN2IEG(Gg)'
    'cKh2lZnytA*2CSd?b>O#o1J#@CZ7(+@e|%keeJCj|M%YF5}q8+&MseHyp{49Y|e=*Z!gaLKX@yczG)|L{DsHLE!_&Yl)Uy>i_h7umwh7S%}06yI!}<xemHzl'
    ')nZ#E579w|zxi?XDOoo{Dxq#yFKVtf+GwT>G>|djg}GfJ$V1zO{WI|EV^aTg`!fc)bl$u%2mz_112?llX8g|?{C0M=7UDwKpC^R;qVO9%tLWIAN0A2lI6bsu'
    'QwI$M{Cz)s-1h-0zcRLgTNAW;r12Jd2np_o_P(y(9Q%Eno|+O4?Y^y-M~obe5;%ZnHqXPs@L`VdFpm+qWjY;KKi#enU1{%6!(4#fLl_^hToELA$&oA>Ysf|E'
    'gp=G`7NeFtFwUJPrUfBQMC6PSE=j3KFa>FW^VB`IL*G>h)R~NaI8wr(w43^Vzk38;mZ9p$)#2&*geCcgyN#%mO)UVPS-FjxPYkD0@Re=2#CN#d^%KRu|F}D1'
    'vZ#dmItN`&ML<=B5FY-z?Q;M9xaNG#fm_I*U~K)>AK0=W+5<Pq4HuXaUQX@C)A0yxf3;YhA9sf^rHAvW|0$FnU3h%@VZYek=y`7Iav0|m2<T4=x58i!_ia~S'
    '`-b}}*p>!K{o#OhaJ>3?LaEHL-9EPCDeT+-T87;1Rxn|<Th8!{MrAx;B&NJ}!Kbx#O0Hvwe4T~PMj4h%D3wfrLn6ri{d&&OcKcNt+T--XJsbLg5Ze0J_0Qoo'
    'YJB^y{yDB{Rqtk!16&_la8o_MuB|cAp<e$bM6>xWte=^4S#kZScxElXUwykI44HoM<q|yuI%JqRadpSQ0~352aQkXL?oYL5o6q!VzG<xf`){}1&))Foe!k(1'
    'RfFC%OIUTj2lTDQV85!Q_ty`Sxf8%p50pO6Xz2Q-n)T!x30YMp9;f<$r5T7}g~Nw{E!ecXP?xJa+QV@_Z`l^|8>n{F``g~Q{^p)n0D-%I8GOFP)@F`wd@j=8'
    '{jJre(rcLeczrI@UsGjX-23xugBh}_=7??gKp{h3XImiLznL1%ax|BwHqAP>!(UFLv(488Pftf0e^GwFI;BM8cvs(*wBvX}rb~b7W}XtP8T-?aXemKWIF`J^'
    '#Ix`&db?qtdMA=k=@~vDBY9)hT?`LRrbAy}-XMm2*FaucY>qHUJ>zz2)AG(`{D8A<TxO%&24?p7^Vrh&4T1mwDm>sabbh%9*Fz3R%!MQ3zzy(tszq7Cna3-d'
    'M}@at^5M-+rz*dY-WJTRu4t>0PDTqIiZ-NeEZpVHSaQmW?5)9%bb(tR3FE3ry2z^@{1AqzEg?<gVm^E6G*7|stRsfmSR4=-jLKO_W~&`?JQkxk_avlr(vVV`'
    'luRUZyf**x>TNL}Fdjxq%-Sq1?0W5d4%`^2GJZ-Fg}4#;mC`WEm@5@4#*ro$w0Y-!O(Jp|G1^W~%Mutv4fmpin4&YVuPmd8Jv38^6+|XIum7wSk}<5Etj0dT'
    'I}#;2=C7B?VG7TdeG!_xwOnKq9c3A%#<M!cj8Rwy6%bT1g}Iz^!IlH*F~T#9!>HPO%aqy*(p>_omL)JAYazH45!uE=xmX{tQz=Sn9!v<>J!Zp8FwO_f$dh6*'
    'Nu@n@5!Uc`OZ11(c8l%etxPItC1X;GqDSF$v?T&Q#Dj?38P2pfNJ$_mw06Lk)SlxBe7m-N@vf^jn)J#LQWB+=0+qIz`9jzh85V=k5f~zAtmZ{an@W+ybuj@+'
    'w=s~ow!f$Qkj_OV7PHTeiX)W_LJx}j<drhc7J;XI44iY+TXN@;!JZ>!Z!-P|ir?Yp^^FIN$7(ap4TXB5TX<0xC<;8X49}2eE)@!iTxe!>PS`var?vEjvG;X7'
    'fZFzp=@bD5Z_rLcBdJI!MbNo4!7?;xA<v?a5umY}X_q2pMcF42agph8ZTe+%Q^)>!hmJ+8mdd)2g~^@=CA`f#XOoJL47hL-ZC@0Y6BfrID<%u)s>sX~W7b_S'
    'vb=~2Z<`7=%jiM|w!tnhAP-(uk`SCk)?kT()6yCpxHdJH*!V>QOnF^OlJBr{3<EZwl?l&HTeQ>OM^%A>u17@#(*<>jTv;uQbKr?wjM1nk*O@z|6*iYK1Z3@<'
    '{dv=SwvA1wD$H^!kXB(+roz!aB5_v;<S2^GMFIOcu%xtu<Yoi>+MH8(haE^qyhsk%hBP?G$jp^Sk1C)8Op!y$mZ@m6QqlShL?KAcr9?(>f3dL^`knLN)p6h@'
    '^N9n9*s>eSHt1Lq^63iv4JELQBq0tM_BOgAfLCTf;VGc0AfeJ;8-IQKS&`#|D*<>hAQ~x|!|VZq4%v&u9K;0G1=N*Ca{#JFGV}o@DZp-CiFajvdEs24Uy?VL'
    'L=>Wyh=*h#RFRA=GB5x=M+een+y?NH0SBPx7|0?@u7gR}wl4=lP^Ax`V`nos+kko%7Qq6x(wvgOX^`1@7%V^!NQZ1PN`+d0=(ttq>GMio(a|7aM$R#%009*Y'
    '$R$}qxCy8L-54Q6B8Z=W-dbLeuMEmpQ9{gK%s$Zm_=4}^1th^Ho1hsadGQR*NJ1;`tg>Kv&m*!TOEg+B0|@|;8fmaR!g{q@|L(3d8)YsYp`z&06LHU!$Qgv_'
    '!M7L)v?+?9A1)Uj3H0bVp*2I)$pMi3(s<Ro-331e8){a3${b9qWw63XEf|?Ht7|sk1qFtKx5_{+0#Ywoipqe9gSfQ+W>j6w8_<-h-9eEU=+B^1S~&reOxAfp'
    'Lz+C)l)K2ZamaeXIFO**^XzbGzUI6gCyX8Rj1!pkISc8KR?r_2e!PVEAlX7h7fk`z7-*IR#BFfdDZ=V8X`4K|GJoCt0hr=WAiu?0SPb3;RS=Elm@l}3mME^#'
    '{RWYkkOHFw(qUjOs9C&9&f5l(pbzgI2f!pmKZF?ZxJw*!3J5=;<q?m_K|rmz;XH$MFn`1#i_|GzT7GSx-6w`7S;Zc3b4ZmGT!~m9R7eG|ZtLubg@O5uQHeYh'
    'RVSnm6q%|RSfbTWKm9j(ktDY'
)
EVALUATION = decode_payload(_ENCODED, PAYLOAD_SHA256)
