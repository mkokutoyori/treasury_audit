from load import *
import re
def enrich(c):
    d=c.DESCRIPTION.fillna('')
    p=d.str.split('|')
    n=d.str.count(r'\|')
    c['CLP_TRADE']=None; c['CLP_XFER']=None; c['CLP_EVENT']=None; c['CLP_PTYPE']=None
    c['CLP_ISSUER']=None; c['CLP_BOOK']=None; c['CLP_SEC']=None; c['CLP_SECDESC']=None
    m9=n==9
    c.loc[m9,'CLP_TRADE']=p[m9].str[1]; c.loc[m9,'CLP_XFER']=p[m9].str[2]
    c.loc[m9,'CLP_EVENT']=p[m9].str[3]; c.loc[m9,'CLP_PTYPE']=p[m9].str[4]
    c.loc[m9,'CLP_ISSUER']=p[m9].str[5]; c.loc[m9,'CLP_BOOK']=p[m9].str[6]
    c.loc[m9,'CLP_SEC']=p[m9].str[7]; c.loc[m9,'CLP_SECDESC']=p[m9].str[8]
    m4=n==4
    c.loc[m4,'CLP_EVENT']=p[m4].str[1]; c.loc[m4,'CLP_BOOK']=p[m4].str[2]; c.loc[m4,'CLP_SEC']=p[m4].str[3]
    m2=n==2
    c.loc[m2,'CLP_EVENT']=p[m2].str[1]; c.loc[m2,'CLP_BOOK']=p[m2].str[2]
    m0=(n==0)&(d.str.contains('/'))
    q=d[m0].str.split('/')
    c.loc[m0,'CLP_EVENT']=q.str[1]; c.loc[m0,'CLP_BOOK']=q.str[2]
    # external ref
    e=c.EXTERNAL_REF_NO.fillna('').str.extract(r'^CLP(\d+)_(\d+)_(\d+)$')
    c['X_TRADE']=e[0]; c['X_XFER']=e[1]; c['X_TIME']=e[2]
    return c
